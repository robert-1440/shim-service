from bean import inject, BeanName
from config import Config
from lambda_pkg.functions import LambdaInvoker
from poll.platform_event.processor import X1440PollingProcessor
from repos.resource_lock import ResourceLockRepo
from tenant.repo import PendingTenantEventRepo


@inject(bean_instances=(BeanName.RESOURCE_LOCK_REPO,
                        BeanName.PENDING_TENANT_EVENTS_REPO,
                        BeanName.LAMBDA_INVOKER,
                        BeanName.CONFIG))
def init(
        resource_lock_repo: ResourceLockRepo,
        pending_tenant_events_repo: PendingTenantEventRepo,
        lambda_invoker: LambdaInvoker,
        config: Config):
    return X1440PollingProcessor(resource_lock_repo, pending_tenant_events_repo, lambda_invoker, config)
