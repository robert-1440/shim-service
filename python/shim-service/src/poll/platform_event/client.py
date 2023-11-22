from typing import Optional

from bean import inject, BeanName
from platform_channels import X1440_PLATFORM
from poll.platform_event import PubSubClientBuilder, PubSubClient, EMPTY_CONTEXT
from repos.sessions_repo import SessionsRepo
from tenant import PendingTenantEvent, TenantContextType, TenantContext
from tenant.repo import TenantContextRepo


@inject(bean_instances=(
        BeanName.PUBSUB_CLIENT_BUILDER,
        BeanName.SESSIONS_REPO,
        BeanName.TENANT_CONTEXT_REPO))
def create_pubsub_client(event: PendingTenantEvent,
                         client_builder: PubSubClientBuilder,
                         sessions_repo: SessionsRepo,
                         tenant_context_repo: TenantContextRepo) -> Optional[PubSubClient]:
    if not sessions_repo.has_sessions_with_platform_channel_type(event.tenant_id, X1440_PLATFORM.name):
        return None
    context = tenant_context_repo.find_context(TenantContextType.X1440, event.tenant_id)
    if context is None:
        context = TenantContext(TenantContextType.X1440, event.tenant_id, 0, EMPTY_CONTEXT)

    return client_builder.build_client(context, event)
