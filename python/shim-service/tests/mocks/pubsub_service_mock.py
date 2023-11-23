import json
import sys
from collections import defaultdict
from datetime import datetime
from queue import Queue, Empty
from threading import Thread, RLock
from typing import Dict, Any, List, Iterable, Tuple, Optional, Callable

from grpc import ChannelCredentials

from generated.platform_event import pubsub_api_pb2 as pb2
from poll.platform_event import Schema, SubscriptionNotification, SubscriptionEvent
from poll.platform_event.pubsub_service import PubSubService, PubSubStream, PubSubChannel, AbstractPubSubStub
from poll.platform_event.stream import PubSubStreamImpl
from support import thread_utils
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


def consume_queue(queue: Queue):
    try:
        while True:
            queue.get_nowait()
            queue.task_done()
    except Empty:
        pass


class RequestHandler:
    def __init__(self, org_id: str, responder: 'MockResponder'):
        self.org_id = org_id
        self.responder = responder
        self.req_queue = Queue()
        self.resp_queue = Queue()
        self.fetcher: Optional[AsyncFetcher] = None
        self.resp_waiting = False
        self.req_waiting = False
        self.mutex = RLock()
        self.done = False
        self.notifications: Dict[str, List[SubscriptionNotification]] = defaultdict(list)

    def add_request(self, req: pb2.FetchRequest):
        if req is None:
            self.log("Saw None request.")
            self.resp_queue.put(None)
        else:
            self.req_queue.put(req)

    def add_response(self, topic: str, resp: SubscriptionNotification):
        notification = self.notifications[topic]
        notification.append(resp)

        self.log(f"Adding response {resp.events[0].payload}")
        self.resp_queue.put(resp)

    def wait_for_request(self) -> Optional[pb2.FetchRequest]:
        def do_wait():
            self.log("Waiting for request ...")
            req = self.req_queue.get()
            self.req_queue.task_done()
            self.log("Done waiting for request ...")
            if req is None:
                return None
            return req

        try:
            with self.mutex:
                if not self.done:
                    self.req_waiting = True
            if self.req_waiting:
                return do_wait()
        finally:
            with self.mutex:
                self.req_waiting = False
            if self.done:
                consume_queue(self.req_queue)
                return None

    def __get_next_notification(self, req: pb2.FetchRequest) -> Optional[SubscriptionNotification]:
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

    def wait_for_response(self, req: pb2.FetchRequest) -> Optional[SubscriptionNotification]:
        def do_wait():
            while not self.done:
                resp = self.resp_queue.get()
                self.resp_queue.task_done()
                if resp is None or self.done:
                    return None
                r = self.__get_next_notification(req)
                if r is not None:
                    return r

        try:
            with self.mutex:
                if not self.done:
                    self.resp_waiting = True
            if self.resp_waiting:
                self.log(f"Waiting for response ...")
                return do_wait()
        finally:
            self.log("Resp done waiting")
            with self.mutex:
                self.resp_waiting = False
            if self.done:
                consume_queue(self.resp_queue)
                return None

    def close(self):
        with self.mutex:
            self.done = True
            self.log(f"Starting close, done={self.done} ...")
            if self.req_waiting:
                self.req_queue.put(None)
            if self.resp_waiting:
                self.resp_queue.put(None)
        if self.resp_waiting:
            self.log("Waiting on response queue ...")
            self.resp_queue.join()
        else:
            self.log("No resp waiting.")
        if self.req_waiting:
            self.log("Waiting on request queue ...")
            self.req_queue.join()
        else:
            self.log("No queue waiting.")
        if self.fetcher is not None:
            self.log("Waiting on fetcher thread...")
            self.fetcher.thread.join(10)
        self.log("Done with close")

    def log(self, text: str):
        print(f"{datetime.now()} {self.org_id} - {text}", file=sys.stderr)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.close()


class AsyncFetcher:
    def __init__(self, fetcher: Iterable[pb2.FetchRequest], handler: RequestHandler):
        self.handler = handler
        self.source = fetcher
        self.thread = thread_utils.start_thread(self.__worker)
        handler.fetcher = self

    def __worker(self):
        try:
            for req in self.source:
                self.handler.add_request(req)
        finally:
            self.handler.log("Sending None request.")
            self.handler.add_request(None)


    def close(self):
        self.thread.join()


class Stream(Iterable[SubscriptionNotification]):
    def __init__(self, handler: RequestHandler):
        self.handler = handler

    def __iter__(self):
        return self

    def __next__(self):
        req = self.handler.wait_for_request()
        if req is None:
            raise StopIteration()
        resp = self.handler.wait_for_response(req)
        if resp is None:
            raise StopIteration()
        return resp


class _Notification(SubscriptionNotification):
    def __init__(self, replay_counter: int, events: List[SubscriptionEvent]):
        self.replay_counter = replay_counter
        self.events = events
        self.latest_replay_id = form_replay_id(replay_counter + 1)


class Controller:
    def __init__(self, responder: 'MockResponder'):
        self.responder = responder
        self.thread: Optional[Thread] = None

    def add_org(self, org_id: str):
        self.responder.get_handler(org_id)

    def invoke(self, caller: Callable):
        self.thread = thread_utils.start_thread(caller)

    def add_notification(self, org_id: str, topic: str, event: Dict[str, Any]):
        self.responder.add_notification(topic, event, org_id)

    def join(self):
        self.responder.cleanup()
        if self.thread is not None:
            self.thread.join(20)
            assert not self.thread.is_alive()

    def wait(self, timeout: float):
        if self.thread is not None:
            self.thread.join(timeout)
            assert not self.thread.is_alive()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.join()


class MockResponder:
    def __init__(self):
        self.notifications: Dict[str, List[SubscriptionNotification]] = defaultdict(list)
        self.handlers: Dict[str, RequestHandler] = {}
        self.async_enabled = False

    def create_request_handler(self, org_id: str):
        self.async_enabled = True
        return self.get_handler(org_id)

    def cleanup(self):
        if len(self.handlers) > 0:
            for h in self.handlers.values():
                h.close()

    def reset(self):
        self.notifications.clear()
        self.handlers.clear()
        self.async_enabled = False

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.cleanup()

    def get_handler(self, org_id: str) -> RequestHandler:
        handler = self.handlers.get(org_id)
        if handler is None:
            handler = RequestHandler(org_id, self)
            self.handlers[org_id] = handler
        return handler

    def add_notification(self, topic: str, event: Dict[str, Any], org_id: str = None):
        converted = json.dumps(event).encode('utf-8')
        forward = SubscriptionEvent()
        forward.schema_id = 'test'
        forward.payload = converted
        notification = self.notifications[topic]
        entry = _Notification(len(notification), [forward])
        notification.append(entry)
        if org_id is not None and self.async_enabled:
            self.get_handler(org_id).add_response(topic, entry)

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


def extract_org_id(metadata: Tuple) -> str:
    for m in metadata:
        if m[0] == 'tenantid':
            return m[1]
    raise ValueError('No tenant id in metadata')


class MockStub(AbstractPubSubStub):
    def __init__(self, responder: MockResponder, channel: MockChannel):
        self.responder = responder
        self.channel = channel
        self.fetcher: Optional[Fetcher] = None

    def subscribe(self, fetch: Iterable[pb2.FetchRequest], metadata: Tuple) -> Iterable[SubscriptionNotification]:
        if self.responder.async_enabled:
            handler = self.responder.get_handler(extract_org_id(metadata))
            AsyncFetcher(fetch, handler)
            return Stream(handler)
        else:
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

    def create_controller(self):
        self.responder.async_enabled = True
        return Controller(self.responder)

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
