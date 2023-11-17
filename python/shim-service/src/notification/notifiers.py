from bean import BeanName, inject
from notification import Notifier


@inject(bean_instances=BeanName.ERROR_NOTIFIER)
def notify_error(notifier: Notifier, subject: str, message: str):
    notifier.notify(subject, message)
