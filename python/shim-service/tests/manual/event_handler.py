import time
from typing import Optional, Callable, Set, Dict

from manual.polling_events import EventListener, PollingEvent, EventType, LoginResultEvent, PresenceStatusChangedEvent, \
    AsyncResultEvent, WorkAssignedEvent, WorkAcceptedEvent, ChatEstablishedEvent, ConversationMessageEvent, \
    ChatRequestEvent
from services.sfdc.live_agent import PresenceStatus, StatusOption
from services.sfdc.live_agent.omnichannel_api import OmniChannelApi, WorkMessage
from support import thread_utils
from utils import collection_utils
from utils.string_utils import uuid


class OurEventListener(EventListener):
    def __init__(self):
        self.api: Optional[OmniChannelApi] = None
        self.logged_in: bool = False
        self.logged_in_async_result = False
        self.presence_status_id: Optional[str] = None
        self.online_status_id: Optional[str] = None
        self.online: bool = False
        self.offline_status_id: Optional[str] = None
        self.work_target_ids: Set[str] = set()
        self.work_ids: Set[str] = set()
        self.work_id_to_target_map: Dict[str, str] = {}
        self.work_target_id_to_work_map: Dict[str, str] = {}
        self.accepted_target_ids: Set[str] = set()
        self.event_map = {
            EventType.LoginResult: self.process_login_result,
            EventType.PresenceStatusChanged: self.process_presence_status_changed,
            EventType.AsyncResult: self.process_async_result,
            EventType.WorkAssigned: self.process_work_assigned,
            EventType.ChatRequest: self.process_chat_request,
            EventType.ChatEstablished: self.process_chat_established,
            EventType.ConversationMessage: self.process_conversation_message
        }

    def set_online(self, api: OmniChannelApi):
        self.api = api
        statuses = self.api.get_presence_statuses()
        online: PresenceStatus = collection_utils.find_first_match(statuses,
                                                                   lambda s: s.status_option == StatusOption.ONLINE)
        assert online is not None
        self.online_status_id = online.id
        offline: PresenceStatus = collection_utils.find_first_match(statuses,
                                                                    lambda s: s.status_option == StatusOption.OFFLINE)
        assert offline is not None
        self.offline_status_id = offline.id
        self.api.set_presence_status(online.id)

    def invoke_close(self, work_id: str):
        def closer():
            time.sleep(3)
            self.api.close_work(work_id)

        thread_utils.start_thread(closer)

    def invoke_offline(self):
        def worker():
            time.sleep(3)
            self.api.set_presence_status(self.offline_status_id)

        thread_utils.start_thread(worker)

    def process_conversation_message(self, event: ConversationMessageEvent):
        text = event.text
        if text is not None:
            if text == "Goodbye.":
                self.invoke_close(event.work_id)
                output = "Goodbye!"
            elif text == "Offline.":
                output = "Going offline now!"
                self.invoke_offline()
            else:
                output = f"You entered: '{text}'?"
            self.send_message(event.work_id, output)

    def send_message(self, work_id: str, text: str):
        message = WorkMessage(
            work_id,
            uuid(),
            text,
            None
        )
        self.api.send_work_message(message)

    def process_chat_request(self, event: ChatRequestEvent):
        work_target_id = event.work_target_id
        work_id = self.work_target_id_to_work_map.get(work_target_id)
        if work_id is not None:
            text = event.messages[0].content
            if text == "Decline":
                self.api.decline_work(work_id, work_target_id, "User said to decline.")
            else:
                self.api.accept_work(work_id, work_target_id)

    def process_chat_established(self, event: ChatEstablishedEvent):
        if event.work_target_id in self.work_target_ids:
            chat_message = event.messages[0]
            self.send_message(event.work_target_id, f"Hello! You entered '{chat_message.content}'?")

    def process_work_accepted(self, event: WorkAcceptedEvent):
        target_id = self.work_id_to_target_map.get(event.work_id)
        if target_id is not None:
            self.accepted_target_ids.add(target_id)

    def process_login_result(self, event: LoginResultEvent):
        if not event.success:
            return
        self.logged_in = True

    def process_presence_status_changed(self, event: PresenceStatusChangedEvent):
        if event.status_id == self.online_status_id:
            self.online = True
        else:
            self.online = False

    def process_work_assigned(self, event: WorkAssignedEvent):
        if self.online and self.logged_in_async_result:
            self.work_target_ids.add(event.work_target_id)
            self.work_ids.add(event.work_id)
            self.work_id_to_target_map[event.work_id] = event.work_target_id
            self.work_target_id_to_work_map[event.work_target_id] = event.work_id

    def process_async_result(self, event: AsyncResultEvent):
        if event.success and not self.logged_in_async_result:
            self.logged_in_async_result = True

    def process(self, event: PollingEvent):
        processor: Callable = self.event_map.get(event.event_type)
        if processor is not None:
            processor(event)
