import os
from bean import inject, BeanName
from config import Config
from lambda_pkg.functions import LambdaInvoker
from poll.platform_event import PubSubClientBuilder
from poll.platform_event.processor import X1440PollingProcessor
from repos.resource_lock import ResourceLockRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from repos.sessions_repo import SessionsRepo
from tenant.repo import PendingTenantEventRepo


@inject(bean_instances=(BeanName.RESOURCE_LOCK_REPO,
                        BeanName.PENDING_TENANT_EVENTS_REPO,
                        BeanName.PUSH_NOTIFICATION_REPO,
                        BeanName.SESSIONS_REPO,
                        BeanName.LAMBDA_INVOKER,
                        BeanName.CONFIG,
                        BeanName.PUBSUB_CLIENT_BUILDER))
def init(
        resource_lock_repo: ResourceLockRepo,
        pending_tenant_events_repo: PendingTenantEventRepo,
        push_notification_repo: SessionPushNotificationsRepo,
        sessions_repo: SessionsRepo,
        lambda_invoker: LambdaInvoker,
        config: Config,
        pubsub_client_builder: PubSubClientBuilder):
    return X1440PollingProcessor(
        resource_lock_repo,
        pending_tenant_events_repo,
        push_notification_repo,
        sessions_repo,
        lambda_invoker,
        config,
        pubsub_client_builder,
        os.environ['PUBSUB_TOPIC'],

    )
