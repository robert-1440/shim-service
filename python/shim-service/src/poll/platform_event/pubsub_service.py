import abc
from typing import Dict, Any, Iterable, Optional, Tuple

from grpc import ChannelCredentials

from generated.platform_event import pubsub_api_pb2 as pb2
from poll.platform_event import SchemaCache, Schema, SubscriptionEvent, SubscriptionNotification
from tenant import TenantContext, PendingTenantEvent


class AbstractPubSubStub(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def subscribe(self, fetch: Iterable[pb2.FetchRequest], metadata: Tuple) -> Iterable[SubscriptionNotification]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_schema(self, request: pb2.SchemaRequest):
        raise NotImplementedError()


class PubSubStream(Iterable[SubscriptionNotification], metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def submit_next(self, replay_id: Optional[bytes]):
        raise NotImplementedError()

    @abc.abstractmethod
    def __iter__(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def decode_event(self, event: SubscriptionEvent) -> Dict[str, Any]:
        raise NotImplementedError()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class PubSubChannel(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def close(self):
        raise NotImplementedError()


class PubSubService(metaclass=abc.ABCMeta):

    def __init__(self):
        self.schema_cache = SchemaCache()

    @abc.abstractmethod
    def create_channel(self, host_and_port: str, credentials: ChannelCredentials):
        raise NotImplementedError()

    @abc.abstractmethod
    def create_stub(self, channel: PubSubChannel) -> AbstractPubSubStub:
        raise NotImplementedError()

    @abc.abstractmethod
    def decode_payload(self, schema: Schema, payload: bytes) -> Dict[str, Any]:
        raise NotImplementedError()

    @abc.abstractmethod
    def create_stream(self,
                      credentials: ChannelCredentials,
                      context: TenantContext,
                      event: PendingTenantEvent,
                      topic: str,
                      timeout_seconds: int) -> PubSubStream:
        raise NotImplementedError()

    def get_schema(self, stub: AbstractPubSubStub, tenant_id: int, schema_id: str) -> Schema:
        def loader():
            request = pb2.SchemaRequest(schema_id=schema_id)
            return stub.get_schema(request)

        schema = self.schema_cache.get_schema(tenant_id, schema_id, loader)

        if schema is None:
            raise ValueError(f"Unable to load schema for tenant id {tenant_id}, schema id {schema_id}")
        return schema
