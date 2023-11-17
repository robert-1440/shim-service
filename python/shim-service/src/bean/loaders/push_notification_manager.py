from typing import Collection

from bean import BeanType, inject
from push_notification import PushNotifier
from push_notification.manager import PushNotificationManager


@inject(bean_types=BeanType.PUSH_NOTIFIER)
def init(notifiers: Collection[PushNotifier]):
    return PushNotificationManager(notifiers)
