import os

from grpc import ChannelCredentials

from bean import inject, BeanName
from config import Config
from lambda_pkg.functions import LambdaInvoker
from poll.platform_event.processor import X1440PollingProcessor
from poll.platform_event.pubsub_service import PubSubService
from repos.resource_lock import ResourceLockRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from repos.sessions_repo import SessionsRepo
from repos.user_sessions import UserSessionsRepo
from repos.work_id_map_repo import WorkIdMapRepo
from tenant.repo import PendingTenantEventRepo, TenantContextRepo


@inject(bean_instances=(BeanName.RESOURCE_LOCK_REPO,
                        BeanName.PENDING_TENANT_EVENTS_REPO,
                        BeanName.PUSH_NOTIFICATION_REPO,
                        BeanName.SESSIONS_REPO,
                        BeanName.USER_SESSIONS_REPO,
                        BeanName.WORK_ID_MAP_REPO,
                        BeanName.TENANT_CONTEXT_REPO,
                        BeanName.LAMBDA_INVOKER,
                        BeanName.CONFIG,
                        BeanName.SECURE_CHANNEL_CREDENTIALS,
                        BeanName.PUBSUB_SERVICE))
def init(
        resource_lock_repo: ResourceLockRepo,
        pending_tenant_events_repo: PendingTenantEventRepo,
        push_notification_repo: SessionPushNotificationsRepo,
        sessions_repo: SessionsRepo,
        user_sessions_repo: UserSessionsRepo,
        work_id_map_repo: WorkIdMapRepo,
        tenant_context_repo: TenantContextRepo,
        lambda_invoker: LambdaInvoker,
        config: Config,
        credentials: ChannelCredentials,
        service: PubSubService):
    return X1440PollingProcessor(
        resource_lock_repo,
        pending_tenant_events_repo,
        push_notification_repo,
        sessions_repo,
        user_sessions_repo,
        work_id_map_repo,
        tenant_context_repo,
        lambda_invoker,
        config,
        os.environ['PUBSUB_TOPIC'],
        credentials,
        service
    )
