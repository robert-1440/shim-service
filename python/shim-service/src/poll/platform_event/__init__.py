import pickle
from typing import List

from poll.platform_event.schema_cache import SchemaCache, Schema


class SubscriptionEvent:
    schema_id: str
    payload: bytes


class SubscriptionNotification:
    events: List[SubscriptionEvent]
    latest_replay_id: bytes


class ContextSettings:
    def __init__(self):
        self.replay_id = None

    def __eq__(self, other):
        return isinstance(other, ContextSettings) and self.replay_id == other.replay_id

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> 'ContextSettings':
        return pickle.loads(data)


EMPTY_CONTEXT = ContextSettings().serialize()
