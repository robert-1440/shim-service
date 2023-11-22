import abc
import pickle
from typing import Optional, Any, Dict, List

from poll.platform_event.schema_cache import SchemaCache, Schema
from tenant import TenantContext, PendingTenantEvent
from utils.enum_utils import ReverseLookupEnum


class ReplayType(ReverseLookupEnum):
    LATEST = "LATEST"
    EARLIEST = "EARLIEST"
    CUSTOM = "CUSTOM"

    @classmethod
    def value_of(cls, value: str):
        return cls._value_of(value, "Replay Type")


class SubscriptionEvent:
    schema_id: str
    payload: bytes


class SubscriptionNotification:
    events: List[SubscriptionEvent]
    latest_replay_id: bytes


class SubscriptionStream(metaclass=abc.ABCMeta):

    def __init__(self, tenant_id: int, cache: SchemaCache):
        self.tenant_id = tenant_id
        self.cache = cache

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def release(self, replay_id: Optional[bytes]):
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def _load_schema(self, schema_id: str) -> Schema:
        raise NotImplementedError()

    @abc.abstractmethod
    def _decode_payload(self, schema: Schema, payload: bytes) -> Dict[str, Any]:
        raise NotImplementedError()

    def decode_event(self, event: SubscriptionEvent) -> Dict[str, Any]:
        schema = self.cache.get_schema(self.tenant_id, event.schema_id, lambda: self._load_schema(event.schema_id))
        return self._decode_payload(schema, event.payload)

    @abc.abstractmethod
    def serialize_context(self) -> bytes:
        raise NotImplementedError()


class PubSubClient(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def create_stream(self,
                      topic: str,
                      timeout_seconds: int,
                      num_requested: int = 1) -> SubscriptionStream:
        raise NotImplementedError()

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError()


class PubSubClientBuilder(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def build_client(self, tenant_context: TenantContext, event: PendingTenantEvent) -> PubSubClient:
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def construct_initial_context_data(cls) -> bytes:
        raise NotImplementedError()


class ContextSettings:
    def __init__(self):
        self.replay_id = None

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> 'ContextSettings':
        return pickle.loads(data)


EMPTY_CONTEXT = ContextSettings().serialize()
