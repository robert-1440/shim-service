from io import BytesIO
from typing import Optional, Dict, Any

import grpc
from avro import schema as avro_schema, io as avro_io
from grpc import ChannelCredentials, Channel

from generated.platform_event import pubsub_api_pb2 as pb2
from generated.platform_event import pubsub_api_pb2_grpc as pb2_grpc
from generated.platform_event.pubsub_api_pb2_grpc import PubSubStub
from poll.platform_event import PubSubClient, ReplayType, SubscriptionStream, PubSubClientBuilder, ContextSettings, \
    EMPTY_CONTEXT, Schema
from poll.platform_event.schema_cache import SchemaCache
from tenant import PendingTenantEvent, TenantContext
from utils.signal_event import SignalEvent
from utils.timer_utils import Timer

_EMPTY_BYTES = b''


class OurStream(SubscriptionStream):

    def __init__(self, client: 'GrpcPubSubClient', topic: str, timeout_seconds: int):
        super().__init__(client.context.tenant_id, client.schema_cache)
        self.client = client
        self.settings = client.settings
        self.source = client.stub.Subscribe(self.fetch)
        self.topic = topic
        self.event_signal = SignalEvent()
        self.closed = False
        self.timeout_seconds = timeout_seconds

    def fetch(self):
        timer = Timer(self.timeout_seconds)
        while not self.closed and timer.has_time_left():
            if self.settings.replay_id is None:
                replay_id = _EMPTY_BYTES
                replay_type = ReplayType.LATEST
            else:
                replay_id = self.settings.replay_id
                replay_type = ReplayType.CUSTOM

            yield pb2.FetchRequest(
                topic_name=self.topic,
                replay_id=replay_id,
                replay_preset=replay_type,
                num_requested=1
            )
            while timer.has_time_left():
                time_left = int(timer.get_delay_time(self.timeout_seconds))
                if self.event_signal.wait(time_left * 1000):
                    break

    def __iter__(self):
        return iter(self.source)

    def close(self):
        if self.closed:
            return
        self.closed = True
        self.event_signal.notify()
        self.client.close()

    def _load_schema(self, schema_id: str) -> Schema:
        schema_json = self.client.stub.GetSchema(pb2.GetSchemaRequest(schema_id=schema_id))
        return avro_schema.parse(schema_json)

    def _decode_payload(self, schema: Schema, payload: bytes) -> Dict[str, Any]:
        buf = BytesIO(payload)
        decoder = avro_io.BinaryDecoder(buf)
        reader = avro_io.DatumReader(schema)
        return reader.read(decoder)

    def release(self, replay_id: Optional[bytes]):
        self.settings.replay_id = replay_id
        self.event_signal.notify()

    def serialize_context(self) -> bytes:
        return self.client.settings.serialize()


class GrpcPubSubClient(PubSubClient):

    def __init__(self, credentials: ChannelCredentials,
                 context: TenantContext,
                 event: PendingTenantEvent,
                 schema_cache: SchemaCache):
        self.context = context
        self.credentials = credentials
        self.schema_cache = schema_cache
        self.metadata = {
            'tenantid': event.org_id,
            'instanceurl': event.instance_url,
            'accesstoken': event.access_token
        }
        self.channel: Optional[Channel] = None
        self.stub: Optional[pb2_grpc.PubSubStub] = None
        self.closed = False
        self.settings = ContextSettings.deserialize(context.data)

    def close(self):
        if not self.closed:
            self.closed = True
            self.channel.close()

    def create_stream(self, topic: str,
                      timeout_seconds: int,
                      num_requested: int = 1) -> SubscriptionStream:
        self.channel = grpc.secure_channel('api.pubsub.salesforce.com:7443', self.credentials)
        good = False
        self.stub = PubSubStub(self.channel)
        try:
            stream = OurStream(self, topic, timeout_seconds)
            good = True
            return stream
        finally:
            if not good:
                self.channel.close()


class GrpcPubSubClientBuilder(PubSubClientBuilder):

    def __init__(self, credentials: ChannelCredentials,
                 schema_cache: SchemaCache):
        self.credentials = credentials
        self.schema_cache = schema_cache

    def build_client(self, context: TenantContext, event: PendingTenantEvent) -> PubSubClient:
        return GrpcPubSubClient(self.credentials, context, event, self.schema_cache)

    @classmethod
    def construct_initial_context_data(cls) -> bytes:
        return EMPTY_CONTEXT
