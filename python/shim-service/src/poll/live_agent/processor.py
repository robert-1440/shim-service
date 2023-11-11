import json
import time
from threading import Thread
from typing import Dict, Any, Optional, List

from bean import InvocableBean
from config import Config
from pending_event import PendingEventType, PendingEvent
from poll import PollingShutdownException
from repos.pending_event_repo import PendingEventsRepo
from repos.resource_lock import ResourceLock, ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from scheduler import Scheduler
from services.sfdc.live_agent import LiveAgentPollerSettings
from services.sfdc.live_agent.message_dispatcher import LiveAgentMessageDispatcher
from services.sfdc.sfdc_session import SfdcSessionAndContext, load_with_context, SfdcSession
from session import SessionContext, ContextType
from utils import loghelper, threading_utils, exception_utils
from utils.date_utils import get_system_time_in_millis, format_elapsed_time_seconds
from utils.threading_utils import ThreadGroup

logger = loghelper.get_logger(__name__)


class LockAndEvent:
    def __init__(self, event: PendingEvent, lock: ResourceLock):
        self.event = event
        self.lock = lock
        self.failed = False

    @property
    def tenant_id(self) -> int:
        return self.event.tenant_id

    @property
    def session_id(self) -> str:
        return self.event.session_id

    def release(self):
        self.lock.release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class LiveAgentPollingProcessor(InvocableBean):

    def __init__(self, pending_events_repo: PendingEventsRepo,
                 resource_lock_repo: ResourceLockRepo,
                 contexts_repo: SessionContextsRepo,
                 scheduler: Scheduler,
                 config: Config,
                 dispatcher: LiveAgentMessageDispatcher):
        self.pe_repo = pending_events_repo
        self.resource_lock_repo = resource_lock_repo
        self.contexts_repo = contexts_repo
        self.scheduler = scheduler
        self.max_sessions = config.sessions_per_live_agent_poll_processor
        self.refresh_seconds = config.live_agent_poll_session_seconds
        self.dispatcher = dispatcher

    def __try_lock(self, event: PendingEvent) -> Optional[LockAndEvent]:
        name = f"lap/{event.tenant_id}-{event.session_id}"
        lock = self.resource_lock_repo.try_acquire(name, self.refresh_seconds)
        if lock is None:
            return None
        if (lock is not None and
                lock.execute_and_release_on_false(lambda:
                                                  self.pe_repo.update_action_time(event, self.refresh_seconds))):
            return LockAndEvent(event, lock)
        return None

    def __invoke_again(self, delay_seconds: int = None):
        self.scheduler.schedule_live_agent_poller(delay_seconds)

    def __collect_keys(self) -> Optional[List[LockAndEvent]]:
        # Sleep for a bit, so we can get as many as possible
        time.sleep(.5)
        result = self.pe_repo.query_events(PendingEventType.LIVE_AGENT_POLL, limit=self.max_sessions)
        if len(result.rows) == 0:
            return None
        output_list = []
        for event in result.rows:
            entry = self.__try_lock(event)
            if entry is not None:
                output_list.append(entry)

        if result.next_token is not None:
            # This means there are more out there
            self.__invoke_again()
        return output_list if len(output_list) > 0 else None

    def __poll(self, sfdc_session: SfdcSession, context: SessionContext):
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
                raise PollingShutdownException()
            return True

        if inner_poll():
            self.contexts_repo.update_session_context(context, settings)

    def __process(self, key: LockAndEvent):
        sc: SfdcSessionAndContext = load_with_context(key, ContextType.LIVE_AGENT)
        if sc is None:
            logger.info(f"Session {key.event} no longer exists.")
            self.pe_repo.delete_event(key.event)
            key.failed = True
            return

        try:
            self.__poll(sc.session, sc.context)
        except BaseException as ex:
            logger.severe(f"Failed during poll: {exception_utils.dump_ex(ex)}")
            message = exception_utils.get_exception_message(ex)
            self.contexts_repo.set_failed(sc.context, message)
            key.failed = True

    def __start_thread(self, key: LockAndEvent) -> Thread:
        def runner():
            with key:
                try:
                    self.__process(key)
                except BaseException as ex:
                    key.failed = True
                    logger.severe(f"Error while processing {key.event}: {exception_utils.dump_ex(ex)}")

        return threading_utils.start_thread(runner, name=f"{key.event}")

    def __release(self, keys: List[LockAndEvent]):
        for key in keys:
            key.release()

    def __touch(self, keys: List[LockAndEvent]):
        entries = map(lambda k: k.event, filter(lambda k: not k.failed, keys))
        self.pe_repo.update_action_times(entries, 0)

    def invoke(self, parameters: Dict[str, Any]):
        keys = self.__collect_keys()
        if keys is None:
            logger.info("No sessions to poll.")
            return

        start_time = get_system_time_in_millis()
        try:
            group = ThreadGroup(list(map(self.__start_thread, keys)))
            logger.info(f"Starting poll for {group.thread_count()} session(s) ...")

            while not group.join(30):
                elapsed = format_elapsed_time_seconds(start_time)
                logger.info(f"Number of threads still running: {group.thread_count()}, up time={elapsed} seconds.")
        finally:
            try:
                self.__release(keys)
                self.__touch(keys)
            finally:
                self.__invoke_again(delay_seconds=5)
                logger.info(f"Stopping, elapsed time = {format_elapsed_time_seconds(start_time)}.")
