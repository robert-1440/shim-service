import json
from collections import defaultdict
from typing import Dict, Any, List, Iterable, Tuple, Optional

from grpc import ChannelCredentials

from generated.platform_event import pubsub_api_pb2 as pb2
from poll.platform_event import Schema, SubscriptionNotification, SubscriptionEvent
from poll.platform_event.pubsub_service import PubSubService, PubSubStream, PubSubChannel, AbstractPubSubStub
from poll.platform_event.stream import PubSubStreamImpl
from tenant import TenantContext, PendingTenantEvent


class MockChannel(PubSubChannel):
    def __init__(self, host_and_port: str, credentials: ChannelCredentials):
        assert credentials is not None
        assert host_and_port is not None
        self.host_and_port = host_and_port
        self.closed = False

    def close(self):
        self.closed = True


class Fetcher(Iterable[SubscriptionNotification]):
    def __init__(self, stub: 'MockStub', fetcher: Iterable[pb2.FetchRequest]):
        self.stub = stub
        self.source = fetcher
        self.__source_it = None

    def __iter__(self):
        assert self.__source_it is None
        self.__source_it = iter(self.source)
        return self

    def __next__(self):
        req = next(self.__source_it)
        resp = self.stub.responder.get_next_notification(req)
        if resp is None:
            raise StopIteration()
        return resp


class _Notification(SubscriptionNotification):
    def __init__(self, replay_counter: int, events: List[SubscriptionEvent]):
        self.replay_counter = replay_counter
        self.events = events
        self.latest_replay_id = form_replay_id(replay_counter + 1)


class MockResponder:
    def __init__(self):
        self.notifications: Dict[str, List[SubscriptionNotification]] = defaultdict(list)

    def add_notification(self, topic: str, event: Dict[str, Any]):
        notification = self.notifications[topic]
        converted = json.dumps(event).encode('utf-8')
        forward = SubscriptionEvent()
        forward.schema_id = 'test'
        forward.payload = converted
        notification.append(_Notification(len(notification), [forward]))

    def get_next_notification(self, req: pb2.FetchRequest) -> Optional[SubscriptionNotification]:
        notification_list = self.notifications.get(req.topic_name)
        if notification_list is None or len(notification_list) == 0:
            return None
        if req.replay_preset == pb2.ReplayPreset.LATEST:
            assert req.replay_id is None or len(req.replay_id) == 0
            index = 0
        else:
            assert req.replay_preset == pb2.ReplayPreset.CUSTOM
            assert req.replay_id is not None
            index = convert_replay_id(req.replay_id)
            if index >= len(notification_list):
                return None

        return notification_list[index]


def form_replay_id(counter: int) -> bytes:
    value = str(counter).rjust(10, '0')
    return value.encode('utf-8')


def convert_replay_id(value: bytes) -> int:
    return int(value.decode('utf-8'))


_SCHEMA = object()


class MockStub(AbstractPubSubStub):
    def __init__(self, responder: MockResponder, channel: MockChannel):
        self.responder = responder
        self.channel = channel
        self.fetcher: Optional[Fetcher] = None

    def subscribe(self, fetch: Iterable[pb2.FetchRequest], metadata: Tuple) -> Iterable[SubscriptionNotification]:
        self.fetcher = Fetcher(self, fetch)
        return self.fetcher

    def get_schema(self, request: pb2.SchemaRequest):
        if request.schema_id == 'test':
            return _SCHEMA
        raise ValueError('Unknown schema id: ' + request.schema_id)


class PubSubServiceMock(PubSubService):

    def __init__(self):
        super(PubSubServiceMock, self).__init__()
        self.channels: List[MockChannel] = []
        self.stubs: List[MockStub] = []
        self.responder: Optional[MockResponder] = MockResponder()

    def pop_stub(self) -> MockStub:
        return self.stubs.pop(0)

    def create_channel(self, host_and_port: str, credentials: ChannelCredentials):
        channel = MockChannel(host_and_port, credentials)
        self.channels.append(channel)
        return channel

    def create_stub(self, channel: MockChannel) -> AbstractPubSubStub:
        stub = MockStub(self.responder, channel)
        self.stubs.append(stub)
        return stub

    def decode_payload(self, schema: Schema, payload: bytes) -> Dict[str, Any]:
        if schema == _SCHEMA:
            return json.loads(payload.decode('utf-8'))
        raise ValueError('Unknown schema: ' + str(schema))

    def create_stream(self, credentials: ChannelCredentials, context: TenantContext, event: PendingTenantEvent,
                      topic: str, timeout_seconds: int) -> PubSubStream:
        return PubSubStreamImpl(self, credentials, context, event, topic, timeout_seconds)
