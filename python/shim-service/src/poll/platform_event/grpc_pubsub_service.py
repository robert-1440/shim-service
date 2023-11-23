from io import BytesIO
from typing import Dict, Any, Iterable, Tuple

import grpc
from avro import schema as avro_schema, io as avro_io
from grpc import ChannelCredentials

from generated.platform_event import pubsub_api_pb2 as pb2
from generated.platform_event.pubsub_api_pb2_grpc import PubSubStub
from poll.platform_event import Schema, SubscriptionNotification
from poll.platform_event.pubsub_service import PubSubService, PubSubStream, PubSubChannel, AbstractPubSubStub
from poll.platform_event.stream import PubSubStreamImpl
from tenant import TenantContext, PendingTenantEvent


class OurStub(AbstractPubSubStub):
    def __init__(self, stub: PubSubStub):
        self.stub = stub

    def subscribe(self, fetch, metadata: Tuple) -> Iterable[SubscriptionNotification]:
        return self.stub.Subscribe(fetch, metadata=metadata)

    def get_schema(self, request: pb2.SchemaRequest):
        schema_json = self.stub.GetSchema(request)
        return avro_schema.parse(schema_json)


class OurChannel(PubSubChannel):
    def __init__(self, channel: grpc.Channel):
        self.channel = channel

    def close(self):
        self.channel.close()


class GrpcPubSubService(PubSubService):

    def create_channel(self, host_and_port: str, credentials: ChannelCredentials):
        return OurChannel(grpc.secure_channel(host_and_port, credentials))

    def create_stub(self, channel: OurChannel) -> AbstractPubSubStub:
        return OurStub(PubSubStub(channel.channel))

    def decode_payload(self, schema: Schema, payload: bytes) -> Dict[str, Any]:
        buf = BytesIO(payload)
        decoder = avro_io.BinaryDecoder(buf)
        reader = avro_io.DatumReader(schema)
        return reader.read(decoder)

    def create_stream(self, credentials: ChannelCredentials, context: TenantContext, event: PendingTenantEvent,
                      topic: str, timeout_seconds: int) -> PubSubStream:
        return PubSubStreamImpl(self, credentials, context, event, topic, timeout_seconds)
