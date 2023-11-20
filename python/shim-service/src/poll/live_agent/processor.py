import json
import time
from threading import Thread, RLock
from typing import Dict, Any, Optional, List, Callable

from config import Config
from lambda_pkg.functions import LambdaInvoker
from lambda_web_framework import InvocableBeanRequestHandler
from pending_event import PendingEventType, PendingEvent
from repos.pending_event_repo import PendingEventsRepo
from repos.resource_lock import ResourceLock, ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from services.sfdc.live_agent import LiveAgentPollerSettings
from services.sfdc.live_agent.message_dispatcher import LiveAgentMessageDispatcher
from services.sfdc.sfdc_session import SfdcSessionAndContext, load_with_context, SfdcSession
from session import SessionContext, ContextType
from utils import loghelper, threading_utils, exception_utils
from utils.date_utils import get_system_time_in_millis, format_elapsed_time_seconds
from utils.signal_event import SignalEvent
from utils.throttler import Throttler
from utils.timer_utils import Timer

logger = loghelper.get_logger(__name__)

_MAX_COLLECT_SECONDS = 10


class LockAndEvent:
    def __init__(self, event: PendingEvent, lock: ResourceLock):
        self.event = event
        self.lock = lock
        self.failed = False
        self.after_release: Optional[Callable] = None

    @property
    def tenant_id(self) -> int:
        return self.event.tenant_id

    @property
    def session_id(self) -> str:
        return self.event.session_id

    def release(self):
        self.lock.release()
        if self.after_release is not None:
            self.after_release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class ProcessorGroup:
    def __init__(self, resource_lock_repo: ResourceLockRepo,
                 pending_event_repo: PendingEventsRepo,
                 contexts_repo: SessionContextsRepo,
                 refresh_seconds: int,
                 max_working_count: int,
                 dispatcher: LiveAgentMessageDispatcher,
                 invoker: LambdaInvoker):
        self.contexts_repo = contexts_repo
        self.resource_lock_repo = resource_lock_repo
        self.max_working_count = max_working_count
        self.pe_repo = pending_event_repo
        self.dispatcher = dispatcher
        self.refresh_seconds = refresh_seconds
        self.threads: List[Thread] = []
        self.submit_count = 0
        self.working_count = 0
        self.invoker = invoker
        self.mutex = RLock()
        self.signal_event = SignalEvent()
        self.invoke_throttler = Throttler(10000, self.invoker.invoke_live_agent_poller)

    def __poll(self, le: LockAndEvent, sfdc_session: SfdcSession, context: SessionContext):
        settings = LiveAgentPollerSettings.deserialize(context.session_data)

        def inner_poll():
            message_data = sfdc_session.poll_live_agent(settings)
            if message_data is None:
                return True

            logger.info(f"Received message data: {json.dumps(message_data.to_record(), indent=True)}")

            messages = settings.add_message_data(message_data)
            for message in messages:
                self.dispatcher.dispatch_message_data(context, message)
            if message_data.is_shutdown_message():
                return False
            return True

        try:
            if inner_poll():
                self.contexts_repo.update_session_context(context, settings)
                self.pe_repo.update_action_time(le.event, 0)
                le.after_release = self.invoke_again
            else:
                logger.info(f"Polling was shut down for {context}.")
                self.contexts_repo.set_failed(context, "Polling was shutdown.")
                self.pe_repo.delete_event(le.event)
        except BaseException as ex:
            message_text = exception_utils.get_exception_message(ex)
            self.contexts_repo.set_failed(context, message_text)
            le.failed = True

    def dec_submit_count(self):
        with self.mutex:
            self.submit_count -= 1
            self.signal_event.notify()

    def invoke_again(self):
        self.invoke_throttler.add_invocation()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.invoke_throttler.close()

    def worker(self, event: PendingEvent):
        # First, try to lock the resource for the event
        le = None
        try:
            le = self.__try_lock(event)
        finally:
            if le is None:
                self.dec_submit_count()
        if le is None:
            return
        with le:
            le.after_release = self.invoke_again

            # Now, load the context
            sc: SfdcSessionAndContext = load_with_context(event, ContextType.LIVE_AGENT)
            if sc is None:
                self.dec_submit_count()
                logger.info(f"Session {event} no longer exists.")
                self.pe_repo.delete_event(event)
                return

            with self.mutex:
                self.working_count += 1
                self.submit_count -= 1
                self.signal_event.notify()
            try:
                self.__poll(le, sc.session, sc.context)
            except BaseException as ex:
                logger.severe(f"Failed during poll: {exception_utils.dump_ex(ex)}")

    def add(self, event: PendingEvent) -> bool:
        """
        Try to add the event for processing.

        :param event: the event.
        :return: False if we are processing the max events.
        """
        if not self.is_full(True):
            t = threading_utils.start_thread(self.worker, user_object=event)
            self.threads.append(t)
            return True
        return False

    def is_empty(self) -> bool:
        return len(self.threads) == 0

    def join(self, timeout: float) -> bool:
        if len(self.threads) == 0:
            return True

        for t in self.threads:
            if not t.is_alive():
                self.threads.remove(t)
                return self.join(timeout)
            else:
                t.join(timeout)
                if not t.is_alive():
                    self.threads.remove(t)
            break

        return len(self.threads) == 0

    def is_full(self, increment: bool = False):
        timer = Timer(_MAX_COLLECT_SECONDS)
        while timer.has_time_left():
            with self.mutex:
                if self.working_count == self.max_working_count:
                    return True
                total = self.working_count + self.submit_count
                if total < self.max_working_count:
                    if increment:
                        self.submit_count += 1
                    return False
            if not increment:
                return False
            self.signal_event.wait(timer.get_delay_time_millis(50))
        return True

    def __try_lock(self, event: PendingEvent) -> Optional[LockAndEvent]:
        # We need to lock on tenant id and user id, since we do not want the same user to be polling more than once
        name = f"lap/{event.tenant_id}-{event.user_id}"
        logger.info(f"Attempting to lock resource {name} ...")
        lock = self.resource_lock_repo.try_acquire(name, self.refresh_seconds)
        if lock is None:
            logger.info(f"{name} is currently locked.")
        elif lock.execute_and_release_on_false(lambda:
                                               self.pe_repo.update_action_time(event, self.refresh_seconds)):
            return LockAndEvent(event, lock)
        return None

    def thread_count(self) -> int:
        return len(self.threads)


class LiveAgentPollingProcessor(InvocableBeanRequestHandler):

    def __init__(self, pending_events_repo: PendingEventsRepo,
                 resource_lock_repo: ResourceLockRepo,
                 contexts_repo: SessionContextsRepo,
                 invoker: LambdaInvoker,
                 config: Config,
                 dispatcher: LiveAgentMessageDispatcher):
        self.pe_repo = pending_events_repo
        self.resource_lock_repo = resource_lock_repo
        self.contexts_repo = contexts_repo
        self.invoker = invoker
        self.max_sessions = config.sessions_per_live_agent_poll_processor
        self.refresh_seconds = config.live_agent_poll_session_seconds
        self.dispatcher = dispatcher

    def collect(self) -> ProcessorGroup:
        group = ProcessorGroup(
            self.resource_lock_repo,
            self.pe_repo,
            self.contexts_repo,
            self.refresh_seconds,
            self.max_sessions,
            self.dispatcher,
            self.invoker
        )
        # Sleep for a bit, so we can get as many as possible
        time.sleep(.5)
        next_token = None
        full = False
        while not full:
            result = self.pe_repo.query_events(
                PendingEventType.LIVE_AGENT_POLL,
                limit=self.max_sessions,
                next_token=next_token
            )
            next_token = result.next_token
            if len(result.rows) == 0:
                if next_token is None:
                    break
            else:
                for event in result.rows:
                    if not group.add(event):
                        full = True
                        break
            if full or next_token is None or group.is_full():
                break

        if full or next_token is not None:
            # This means we have more than the max out there, let another process grab them
            group.invoke_again()

        return group

    def invoke(self, parameters: Dict[str, Any]):

        # We want to lock during collection to avoid as many collisions on individual events found as possible
        lock = self.resource_lock_repo.try_acquire("lap-collect", _MAX_COLLECT_SECONDS + 2)
        if lock is None:
            logger.info("Another poller is collecting sessions.")
            return

        with lock:
            group = self.collect()

        if group.is_empty():
            logger.info("No sessions to poll.")
            return

        start_time = get_system_time_in_millis()
        try:
            logger.info(f"Starting poll for {group.thread_count()} session(s) ...")

            with group:
                while not group.join(30):
                    elapsed = format_elapsed_time_seconds(start_time)
                    logger.info(f"Number of threads still running: {group.thread_count()}, up time={elapsed} seconds.")
        finally:
            logger.info(f"Stopping, elapsed time = {format_elapsed_time_seconds(start_time)}.")
