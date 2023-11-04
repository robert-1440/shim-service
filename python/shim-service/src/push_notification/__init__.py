import abc
import pickle
from traceback import print_exc
from typing import Dict, Optional

from bean import BeanInitializationException
from session import SessionKey
from utils import exception_utils
from utils.date_utils import EpochMilliseconds


class PushNotificationContextSettings:
    def __init__(self, last_seq_no: int = None):
        self.last_seq_no = last_seq_no

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> 'PushNotificationContextSettings':
        return pickle.loads(data)

    def __eq__(self, other):
        return isinstance(other, PushNotificationContextSettings) and self.last_seq_no == other.last_seq_no


class SessionPushNotification(SessionKey):
    def __init__(self,
                 tenant_id: int,
                 session_id: str,
                 seq_no: int,
                 platform_channel_type: str,
                 message_type: str,
                 message: str,
                 time_created: EpochMilliseconds,
                 sent: bool = False):
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.seq_no = seq_no
        self.platform_channel_type = platform_channel_type
        self.message_type = message_type
        self.message = message
        self.sent = sent
        self.time_created = time_created


class PushNotifier(metaclass=abc.ABCMeta):

    def send_push_notification(self, token: str, data: Dict[str, str]):
        self._notify(token, data)

    def test_push_notification(self, token: str) -> Optional[str]:
        """
        Attempt a push notification as a dry-run.

        :param token: the FCM device token.
        :return: None if the test passed, otherwise a string with the error message.
        """
        record = {'type': 'validation'}
        try:
            self._notify(token, record, dry_run=True)
        except BeanInitializationException as ex:
            raise ex
        except Exception as ex:
            print_exc()
            return exception_utils.get_exception_message(ex)
        return None

    @abc.abstractmethod
    def _notify(self, token: str, data: Dict[str, str], dry_run: bool = False):
        raise NotImplementedError()

    @classmethod
    def get_token_prefix(cls) -> Optional[str]:
        return None
