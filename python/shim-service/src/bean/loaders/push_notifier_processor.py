from bean import BeanName
from bean.beans import inject
from push_notification.manager import PushNotificationManager
from push_notification.processor import PushNotificationProcessor
from repos.session_contexts import SessionContextsRepo
from repos.session_push_notifications import SessionPushNotificationsRepo


@inject(bean_instances=(
        BeanName.SESSION_CONTEXTS_REPO,
        BeanName.PUSH_NOTIFICATION_REPO,
        BeanName.PUSH_NOTIFICATION_MANAGER
))
def init(session_contexts_repo: SessionContextsRepo,
         push_notification_repo: SessionPushNotificationsRepo,
         push_notification_manager: PushNotificationManager):
    return PushNotificationProcessor(
        session_contexts_repo,
        push_notification_repo,
        push_notification_manager
    )
