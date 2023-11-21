from typing import Any

from config import Config
from lambda_pkg.functions import LambdaInvoker
from poll.base_processor import BasePollingProcessor
from poll.platform_event.session import create_platform_event_session, PlatformEventSession
from poll.polling_group import AbstractProcessorGroup, E, LockAndEvent
from repos import QueryResult
from repos.resource_lock import ResourceLockRepo
from tenant import PendingTenantEvent, PendingTenantEventType
from tenant.repo import PendingTenantEventRepo
from utils import loghelper

_MAX_COLLECT_SECONDS = 10

logger = loghelper.get_logger(__name__)


class ProcessorGroup(AbstractProcessorGroup):
    def __init__(self,
                 resource_lock_repo: ResourceLockRepo,
                 pending_tenant_events_repo: PendingTenantEventRepo,
                 lambda_invoker: LambdaInvoker,
                 refresh_seconds: int,
                 max_working_count: int,
                 max_collect_seconds: int, ):
        super().__init__(resource_lock_repo, refresh_seconds, max_working_count, max_collect_seconds)
        self.pending_tenant_events_repo = pending_tenant_events_repo
        self.lambda_invoker = lambda_invoker

    def form_lock_name(self, event: PendingTenantEvent):
        return f"pubsub-{event.tenant_id}"

    def invoke_lambda(self):
        self.lambda_invoker.invoke_sfdc_pubsub_poller()

    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        return self.pending_tenant_events_repo.update_action_time(event, seconds_in_future)

    def should_poll(self, le: LockAndEvent) -> bool:
        polling_session = create_platform_event_session(le.event.tenant_id)
        if polling_session is None:
            logger.info(f"Tenant {le.event.tenant_id} has no sessions to poll.")
            self.pending_tenant_events_repo.delete_event(le.event)
            return False
        le.user_object = polling_session
        return True

    def poll(self, le: LockAndEvent):
        session: PlatformEventSession = le.user_object
        session.poll()

    def query_events(self, limit: int, next_token: Any) -> QueryResult:
        return self.pending_tenant_events_repo.query_events(PendingTenantEventType.X1440_POLL, limit, next_token)


class X1440PollingProcessor(BasePollingProcessor):

    def __init__(self,
                 resource_lock_repo: ResourceLockRepo,
                 pending_tenant_event_repo: PendingTenantEventRepo,
                 lambda_invoker: LambdaInvoker,
                 config: Config):
        super().__init__(resource_lock_repo, _MAX_COLLECT_SECONDS)
        self.pending_tenant_event_repo = pending_tenant_event_repo
        self.lambda_invoker = lambda_invoker
        self.max_sessions = config.sessions_per_pubsub_poll_processor
        self.refresh_seconds = config.pubsub_poll_session_seconds

    @classmethod
    def lock_name(cls) -> str:
        return "pubsub-collect"

    def create_group(self) -> AbstractProcessorGroup:
        return ProcessorGroup(
            self.resource_lock_repo,
            self.pending_tenant_event_repo,
            self.lambda_invoker,
            self.refresh_seconds,
            self.max_sessions,
            _MAX_COLLECT_SECONDS
        )
