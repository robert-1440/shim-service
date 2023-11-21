import abc
from typing import Callable, Optional

from poll import PollingPlatform
from session import ContextType
from utils.enum_utils import ReverseLookupEnum


class ReplayType(ReverseLookupEnum):
    LATEST = "LATEST"
    EARLIEST = "EARLIEST"
    CUSTOM = "CUSTOM"

    @classmethod
    def value_of(cls, value: str):
        return cls._value_of(value, "Replay Type")


class SubscriptionStream(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def cancel(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def release(self, replay_id: Optional[bytes]):
        raise NotImplementedError()


class PubSubClient(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def subscribe(self,
                  topic: str,
                  replay_type: ReplayType,
                  replay_id: Optional[bytes],
                  num_requested: int,
                  callback: Callable) -> SubscriptionStream:
        raise NotImplementedError()
