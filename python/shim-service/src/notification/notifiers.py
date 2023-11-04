from bean import BeanName
from bean.beans import inject
from notification import Notifier


@inject(bean_instances=BeanName.ERROR_NOTIFIER)
def notify_error(notifier: Notifier, subject: str, message: str):
    notifier.notify(subject, message)
