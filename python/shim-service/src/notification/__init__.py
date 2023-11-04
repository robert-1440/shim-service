import abc
from enum import Enum
from typing import Optional, List


class SubscriptionStatus(Enum):
    PENDING = "Pending"
    CONFIRMED = 'Confirmed'


class Subscription:
    def __init__(self, email_address: str,
                 external_id: str = None,
                 status: Optional[SubscriptionStatus] = None):
        self.email_address = email_address
        self.external_id = external_id
        self.status = status


class Notifier(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def notify(self, subject: str, message: str):
        raise NotImplementedError()

    @abc.abstractmethod
    def subscribe(self, subscription: Subscription) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def unsubscribe(self, subscription: Subscription):
        raise NotImplementedError()

    @abc.abstractmethod
    def list_subscriptions(self) -> List[Subscription]:
        raise NotImplementedError()

    @abc.abstractmethod
    def find_subscription(self, email_address: str) -> Optional[Subscription]:
        raise NotImplementedError()
