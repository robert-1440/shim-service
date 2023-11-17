from bean import BeanName, inject
from repos.session_push_notifications import SessionPushNotificationsRepo
from services.sfdc.live_agent.message_dispatcher import LiveAgentMessageDispatcher


@inject(bean_instances=BeanName.PUSH_NOTIFICATION_REPO)
def init(repo: SessionPushNotificationsRepo):
    return LiveAgentMessageDispatcher(repo)
