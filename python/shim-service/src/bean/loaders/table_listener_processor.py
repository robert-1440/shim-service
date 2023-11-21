from bean import BeanName, inject
from lambda_pkg.functions import LambdaInvoker
from repos.session_contexts import SessionContextsRepo
from table_listener.processor import TableListenerProcessor
from tenant.repo import PendingTenantEventRepo


@inject(bean_instances=(BeanName.SESSION_CONTEXTS_REPO,
                        BeanName.PENDING_TENANT_EVENTS_REPO,
                        BeanName.LAMBDA_INVOKER))
def init(repo: SessionContextsRepo, pending_tenant_event_repo: PendingTenantEventRepo,
         lambda_invoker: LambdaInvoker):
    return TableListenerProcessor(repo, pending_tenant_event_repo, lambda_invoker)
