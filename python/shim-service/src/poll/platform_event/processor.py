import json
from typing import Any, Dict, Optional

from grpc import ChannelCredentials

from config import Config
from lambda_pkg.functions import LambdaInvoker
from platform_channels import X1440_PLATFORM
from poll.base_processor import BasePollingProcessor
from poll.platform_event import EMPTY_CONTEXT
from poll.platform_event.pubsub_service import PubSubService, PubSubStream
from poll.polling_group import AbstractProcessorGroup, LockAndEvent
from repos import QueryResult
from repos.resource_lock import ResourceLockRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from repos.sessions_repo import SessionsRepo
from repos.user_sessions import UserSessionsRepo
from repos.work_id_map_repo import WorkIdMapRepo
from session import SessionKeyAndUser
from tenant import PendingTenantEvent, PendingTenantEventType, TenantContextType, TenantContext
from tenant.repo import PendingTenantEventRepo, TenantContextRepo
from utils import loghelper

_MAX_COLLECT_SECONDS = 10

logger = loghelper.get_logger(__name__)

_USER_ID_FIELD = 'RS_L__User_Id__c'
_CONVERSATION_ID_FIELD = 'RS_L__Conversation_Id__c'
_MESSAGE_TYPE_FIELD = 'RS_L_Type__c'


class ProcessorGroup(AbstractProcessorGroup):
    def __init__(self,
                 processor: 'X1440PollingProcessor',
                 max_collect_seconds: int):
        super().__init__(processor.resource_lock_repo, processor.refresh_seconds,
                         processor.max_sessions, max_collect_seconds)
        self.pending_tenant_events_repo = processor.pending_tenant_event_repo
        self.sessions_repo = processor.sessions_repo
        self.service = processor.pubsub_service
        self.lambda_invoker = processor.lambda_invoker
        self.topic = processor.topic
        self.user_sessions_repo = processor.user_sessions_repo
        self.work_id_map_repo = processor.work_id_map_repo
        self.push_notifier_repo = processor.push_notifier_repo
        self.tenant_context_repo = processor.tenant_context_repo
        self.credentials = processor.credentials

    def form_lock_name(self, event: PendingTenantEvent):
        return f"pubsub-{event.tenant_id}"

    def invoke_lambda(self):
        self.lambda_invoker.invoke_sfdc_pubsub_poller()

    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        return self.pending_tenant_events_repo.update_action_time(event, seconds_in_future)

    def should_poll(self, le: LockAndEvent) -> bool:
        event: PendingTenantEvent = le.event
        if not self.sessions_repo.has_sessions_with_platform_channel_type(event.tenant_id, X1440_PLATFORM.name):
            logger.info(f"Tenant {le.event.tenant_id} has no sessions.")
            self.pending_tenant_events_repo.delete_event(le.event)
            return False

        context = self.tenant_context_repo.find_context(TenantContextType.X1440, event.tenant_id)
        if context is None:
            context = TenantContext(TenantContextType.X1440, event.tenant_id, 0, EMPTY_CONTEXT)

        le.user_object = self.service.create_stream(
            self.credentials,
            context,
            event,
            self.topic,
            self.refresh_seconds
        )
        return True

    def __inner_poll(self, tenant_id: int, stream: PubSubStream):
        with stream:
            for notification_record in stream:
                for event in notification_record.events:
                    decoded = stream.decode_event(event)
                    logger.info(f"Received message:\n{json.dumps(decoded, indent=True)}")
                    self.__dispatch(tenant_id, decoded)
                stream.submit_next(notification_record.latest_replay_id)

    def poll(self, le: LockAndEvent):
        tenant_id = le.event.tenant_id
        stream: PubSubStream = le.user_object
        self.__inner_poll(tenant_id, stream)

    def query_events(self, limit: int, next_token: Any) -> QueryResult:
        return self.pending_tenant_events_repo.query_events(PendingTenantEventType.X1440_POLL, limit, next_token)

    def __resolve_session_id(self, tenant_id: int, message: Dict[str, Any]) -> Optional[SessionKeyAndUser]:
        user_id = message.get(_USER_ID_FIELD)
        conversation_id = message.get(_CONVERSATION_ID_FIELD)
        session_id = None
        result_user_id = None

        if conversation_id is not None:
            work = self.work_id_map_repo.find_work(tenant_id, conversation_id)
            if work is not None:
                session_id = work.session_id
                result_user_id = user_id or work.user_id

        if session_id is None and user_id is not None:
            user_session = self.user_sessions_repo.find_user_session(tenant_id, user_id)
            if user_session is not None:
                session_id = user_session.session_id
                result_user_id = user_id

        if session_id is None:
            logger.warning(f"Unable to resolve session for following message:\n{json.dumps(message, indent=True)}")
            return None
        return SessionKeyAndUser.user_key_of(tenant_id, session_id, result_user_id)

    def __dispatch(self, tenant_id: int, message: Dict[str, Any]):
        key = self.__resolve_session_id(tenant_id, message)
        if key is None:
            return
        message_type = message.get(_MESSAGE_TYPE_FIELD, "?")
        self.push_notifier_repo.submit(key, X1440_PLATFORM.name, message_type, json.dumps(message))


class X1440PollingProcessor(BasePollingProcessor):

    def __init__(self,
                 resource_lock_repo: ResourceLockRepo,
                 pending_tenant_event_repo: PendingTenantEventRepo,
                 push_notifier_repo: SessionPushNotificationsRepo,
                 sessions_repo: SessionsRepo,
                 user_sessions_repo: UserSessionsRepo,
                 work_id_map_repo: WorkIdMapRepo,
                 tenant_context_repo: TenantContextRepo,
                 lambda_invoker: LambdaInvoker,
                 config: Config,
                 topic: str,
                 credentials: ChannelCredentials,
                 pubsub_service: PubSubService):
        super().__init__(resource_lock_repo, _MAX_COLLECT_SECONDS)
        self.pending_tenant_event_repo = pending_tenant_event_repo
        self.sessions_repo = sessions_repo
        self.user_sessions_repo = user_sessions_repo
        self.credentials = credentials
        self.work_id_map_repo = work_id_map_repo
        self.tenant_context_repo = tenant_context_repo
        self.lambda_invoker = lambda_invoker
        self.max_sessions = config.sessions_per_pubsub_poll_processor
        self.refresh_seconds = config.pubsub_poll_session_seconds
        self.topic = topic
        self.pubsub_service = pubsub_service
        self.push_notifier_repo = push_notifier_repo

    @classmethod
    def lock_name(cls) -> str:
        return "pubsub-collect"

    def create_group(self) -> AbstractProcessorGroup:
        return ProcessorGroup(self, _MAX_COLLECT_SECONDS)
