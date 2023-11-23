from copy import copy
from typing import Optional, Dict, Any

from grpc import ChannelCredentials

from generated.platform_event import pubsub_api_pb2 as pb2
from poll.platform_event import ContextSettings, SubscriptionEvent
from poll.platform_event.pubsub_service import PubSubChannel, AbstractPubSubStub, PubSubService, PubSubStream
from tenant import PendingTenantEvent, TenantContext
from tenant.repo import set_context_data
from utils import loghelper
from utils.byte_utils import EMPTY_BYTES
from utils.signal_event import SignalEvent
from utils.timer_utils import Timer

logger = loghelper.get_logger(__name__)


class PubSubStreamImpl(PubSubStream):
    def __init__(self,
                 service: PubSubService,
                 credentials: ChannelCredentials,
                 context: TenantContext,
                 event: PendingTenantEvent,
                 topic: str,
                 timeout_seconds: int):
        self.topic = topic
        self.context = context
        self.tenant_id = context.tenant_id
        self.settings = ContextSettings.deserialize(context.data)
        self.initial_settings = copy(self.settings)
        self.service = service
        self.credentials = credentials
        self.metadata = (('accesstoken', event.access_token),
                         ('instanceurl', event.instance_url),
                         ('tenantid', event.org_id))
        self.timeout_seconds = timeout_seconds
        self.channel: Optional[PubSubChannel] = None
        self.stub: Optional[AbstractPubSubStub] = None
        self.event_signal: Optional[SignalEvent] = None
        self.closed = False

    def __fetch(self):
        logger.info(f"[{self.tenant_id}] Starting fetch loop, timeout is {self.timeout_seconds} seconds.")
        timer = Timer(self.timeout_seconds)
        while not self.closed and timer.has_time_left():
            if self.settings.replay_id is None:
                replay_id = EMPTY_BYTES
                replay_preset = pb2.ReplayPreset.LATEST
            else:
                replay_id = self.settings.replay_id
                replay_preset = pb2.ReplayPreset.CUSTOM

            yield pb2.FetchRequest(
                topic_name=self.topic,
                replay_id=replay_id,
                replay_preset=replay_preset,
                num_requested=1
            )
            while not self.closed and timer.has_time_left():
                time_left = int(timer.get_delay_time(self.timeout_seconds))
                if self.event_signal.wait(time_left * 1000):
                    break
        logger.info(f"[{self.tenant_id}] Fetch loop ended.")

    def submit_next(self, replay_id: Optional[bytes]):
        self.settings.replay_id = replay_id
        self.event_signal.notify()

    def decode_event(self, event: SubscriptionEvent) -> Dict[str, Any]:
        schema = self.service.get_schema(self.stub, self.tenant_id, event.schema_id)
        return self.service.decode_payload(schema, event.payload)

    def __iter__(self):
        assert self.stub is None
        self.channel = self.service.create_channel('api.pubsub.salesforce.com:7443', self.credentials)
        self.stub = self.service.create_stub(self.channel)
        self.event_signal = SignalEvent()
        return iter(self.stub.subscribe(self.__fetch(), self.metadata))

    def close(self):
        if not self.closed:
            self.closed = True
            if self.event_signal is not None:
                self.event_signal.notify(keep_signalled=True)

            if self.channel is not None:
                self.channel.close()
            if self.settings != self.initial_settings:
                set_context_data(self.context, self.settings.serialize())
