import abc
from typing import Iterable

from push_notification import SessionPushNotification
from session import SessionContext, SessionKey


class SessionPushNotificationsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def submit(self, context: SessionContext, platform_channel_type: str, message_type: str, message: str):
        raise NotImplementedError()

    @abc.abstractmethod
    def query_notifications(self,
                            session_key: SessionKey,
                            previous_seq_no: int = None) -> Iterable[SessionPushNotification]:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_sent(self, record: SessionPushNotification, context: SessionContext = None) -> bool:
        raise NotImplementedError()
