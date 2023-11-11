from bean import BeanName
from bean.beans import inject
from config import Config
from poll.live_agent.processor import LiveAgentPollingProcessor
from repos.pending_event_repo import PendingEventsRepo
from repos.resource_lock import ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from scheduler import Scheduler
from services.sfdc.live_agent.message_dispatcher import LiveAgentMessageDispatcher


@inject(bean_instances=(BeanName.PENDING_EVENTS_REPO,
                        BeanName.RESOURCE_LOCK_REPO,
                        BeanName.SESSION_CONTEXTS_REPO,
                        BeanName.SCHEDULER,
                        BeanName.CONFIG,
                        BeanName.LIVE_AGENT_MESSAGE_DISPATCHER))
def init(pending_events_repo: PendingEventsRepo,
         resource_lock_repo: ResourceLockRepo,
         contexts_repo: SessionContextsRepo,
         scheduler: Scheduler,
         config: Config,
         dispatcher: LiveAgentMessageDispatcher
         ):
    return LiveAgentPollingProcessor(
        pending_events_repo,
        resource_lock_repo,
        contexts_repo,
        scheduler,
        config,
        dispatcher
    )
