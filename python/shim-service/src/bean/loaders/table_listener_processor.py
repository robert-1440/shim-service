from bean import BeanName
from bean.beans import inject
from repos.session_contexts import SessionContextsRepo
from table_listener.processor import TableListenerProcessor


@inject(bean_instances=BeanName.SESSION_CONTEXTS_REPO)
def init(repo: SessionContextsRepo):
    return TableListenerProcessor(repo)
