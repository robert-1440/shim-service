from typing import Any, Dict

from config import Config
from lambda_pkg.functions import LambdaInvoker
from poll.base_processor import BasePollingProcessor
from poll.platform_event import PubSubClientBuilder, PubSubClient, SubscriptionNotification
from poll.polling_group import AbstractProcessorGroup, LockAndEvent
from repos import QueryResult
from repos.resource_lock import ResourceLockRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from repos.sessions_repo import SessionsRepo
from tenant import PendingTenantEvent, PendingTenantEventType
from tenant.repo import PendingTenantEventRepo
from utils import loghelper

_MAX_COLLECT_SECONDS = 10

logger = loghelper.get_logger(__name__)


class ProcessorGroup(AbstractProcessorGroup):
    def __init__(self,
                 processor: 'X1440PollingProcessor',
                 max_collect_seconds: int):
        super().__init__(processor.resource_lock_repo, processor.refresh_seconds,
                         processor.max_sessions, max_collect_seconds)
        self.pending_tenant_events_repo = processor.pending_tenant_event_repo
        self.client_builder = processor.pubsub_client_builder
        self.lambda_invoker = processor.lambda_invoker
        self.topic = processor.topic

    def form_lock_name(self, event: PendingTenantEvent):
        return f"pubsub-{event.tenant_id}"

    def invoke_lambda(self):
        self.lambda_invoker.invoke_sfdc_pubsub_poller()

    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        return self.pending_tenant_events_repo.update_action_time(event, seconds_in_future)

    def should_poll(self, le: LockAndEvent) -> bool:
        client = self.client_builder.build_client(le.user_object, le.event)
        if client is None:
            logger.info(f"Tenant {le.event.tenant_id} has no sessions.")
            self.pending_tenant_events_repo.delete_event(le.event)
            return False
        le.user_object = client
        return True

    def dispatch(self, tenant_id: int, message: Dict[str, Any]):
        pass

    def poll(self, le: LockAndEvent):
        tenant_id = le.event.tenant_id
        client: PubSubClient = le.user_object
        with client.create_stream(self.topic, self.refresh_seconds) as stream:
            for notification_record in stream:
                notification_record: SubscriptionNotification
                for event in notification_record.events:
                    decoded = stream.decode_event(event)
                    self.dispatch(tenant_id, decoded)
                stream.release(notification_record.latest_replay_id)

    def query_events(self, limit: int, next_token: Any) -> QueryResult:
        return self.pending_tenant_events_repo.query_events(PendingTenantEventType.X1440_POLL, limit, next_token)


class X1440PollingProcessor(BasePollingProcessor):

    def __init__(self,
                 resource_lock_repo: ResourceLockRepo,
                 pending_tenant_event_repo: PendingTenantEventRepo,
                 push_notifier_repo: SessionPushNotificationsRepo,
                 sessions_repo: SessionsRepo,
                 lambda_invoker: LambdaInvoker,
                 config: Config,
                 pubsub_client_builder: PubSubClientBuilder,
                 topic: str):
        super().__init__(resource_lock_repo, _MAX_COLLECT_SECONDS)
        self.pending_tenant_event_repo = pending_tenant_event_repo
        self.sessions_repo = sessions_repo
        self.lambda_invoker = lambda_invoker
        self.max_sessions = config.sessions_per_pubsub_poll_processor
        self.refresh_seconds = config.pubsub_poll_session_seconds
        self.topic = topic
        self.pubsub_client_builder = pubsub_client_builder
        self.push_notifier_repo = push_notifier_repo

    @classmethod
    def lock_name(cls) -> str:
        return "pubsub-collect"

    def create_group(self) -> AbstractProcessorGroup:
        return ProcessorGroup(self, _MAX_COLLECT_SECONDS)
