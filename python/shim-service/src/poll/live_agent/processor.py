import json
from typing import Any

from config import Config
from lambda_pkg.functions import LambdaInvoker
from pending_event import PendingEventType
from poll.base_processor import BasePollingProcessor
from poll.polling_group import AbstractProcessorGroup, LockAndEvent, E
from repos import QueryResult
from repos.pending_event_repo import PendingEventsRepo
from repos.resource_lock import ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from services.sfdc.live_agent import LiveAgentPollerSettings
from services.sfdc.live_agent.message_dispatcher import LiveAgentMessageDispatcher
from services.sfdc.sfdc_session import SfdcSessionAndContext, load_with_context
from session import ContextType
from utils import loghelper, exception_utils

logger = loghelper.get_logger(__name__)

_MAX_COLLECT_SECONDS = 10


class ProcessorGroup(AbstractProcessorGroup):
    def __init__(self, resource_lock_repo: ResourceLockRepo,
                 pending_event_repo: PendingEventsRepo,
                 contexts_repo: SessionContextsRepo,
                 refresh_seconds: int,
                 max_working_count: int,
                 dispatcher: LiveAgentMessageDispatcher,
                 invoker: LambdaInvoker):
        super().__init__(resource_lock_repo, refresh_seconds, max_working_count, _MAX_COLLECT_SECONDS)
        self.contexts_repo = contexts_repo
        self.pe_repo = pending_event_repo
        self.dispatcher = dispatcher
        self.invoker = invoker

    def invoke_lambda(self):
        self.invoker.invoke_live_agent_poller()

    def poll(self, le: LockAndEvent):
        sc: SfdcSessionAndContext = le.user_object
        sfdc_session = sc.session
        context = sc.context
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

    def should_poll(self, le: LockAndEvent) -> bool:
        sc: SfdcSessionAndContext = load_with_context(le.event, ContextType.LIVE_AGENT)
        if sc is None:
            logger.info(f"Session {le.event} no longer exists.")
            self.pe_repo.delete_event(le.event)
            return False
        le.user_object = sc
        return True

    def form_lock_name(self, event: E):
        return f"lap/{event.tenant_id}-{event.user_id}"

    def update_action_time(self, event: E, seconds_in_future: int) -> bool:
        return self.pe_repo.update_action_time(event, seconds_in_future)

    def query_events(self, limit: int, next_token: Any) -> QueryResult:
        return self.pe_repo.query_events(
            PendingEventType.LIVE_AGENT_POLL,
            limit=limit,
            next_token=next_token
        )


class LiveAgentPollingProcessor(BasePollingProcessor):

    def __init__(self, pending_events_repo: PendingEventsRepo,
                 resource_lock_repo: ResourceLockRepo,
                 contexts_repo: SessionContextsRepo,
                 invoker: LambdaInvoker,
                 config: Config,
                 dispatcher: LiveAgentMessageDispatcher):
        super().__init__(resource_lock_repo, _MAX_COLLECT_SECONDS)
        self.pe_repo = pending_events_repo
        self.resource_lock_repo = resource_lock_repo
        self.contexts_repo = contexts_repo
        self.invoker = invoker
        self.max_sessions = config.sessions_per_live_agent_poll_processor
        self.refresh_seconds = config.live_agent_poll_session_seconds
        self.dispatcher = dispatcher

    @classmethod
    def lock_name(cls) -> str:
        return "lap-collect"

    def create_group(self) -> AbstractProcessorGroup:
        return ProcessorGroup(
            self.resource_lock_repo,
            self.pe_repo,
            self.contexts_repo,
            self.refresh_seconds,
            self.max_sessions,
            self.dispatcher,
            self.invoker
        )
