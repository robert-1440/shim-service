import abc
from typing import Optional, Dict, Any, Tuple, Callable

from utils.enum_utils import ReverseLookupEnum


class PollingEvent(metaclass=abc.ABCMeta):
    event_type: 'EventType'

    @classmethod
    def construct_event(cls, message_type: str, message_data: Dict[str, Any]) -> Optional['PollingEvent']:
        et = EventType.find_type(message_type)
        if et is not None:
            event = et.value[1](message_data)
            event.event_type = et
            return event
        return None


class LoginResultEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.success = event_data['success']
        user_info = event_data['userInfo']
        self.user_name = user_info['fullName']
        self.user_id = user_info['id']


class AsyncResultEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.sequence = event_data['sequence']
        self.success = event_data['isSuccess']


class WorkAssignedEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.work_id: str = event_data['workId']
        self.work_target_id: str = event_data['workTargetId']
        self.channel_name: str = event_data['channelName']


class PresenceStatusChangedEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        status = event_data['status']
        self.status_id = status['statusId']
        details = status['statusDetails']
        self.status_name = details['statusName']


class WorkAcceptedEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.work_id: str = event_data['workId']


class ChatMessage:
    def __init__(self, node: dict):
        self.sequence: int = node['sequence']
        self.content: str = node.get('content')
        self.entry_type: str = node['entryType']


class ChatRequestEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.work_target_id = event_data['workTargetId']
        self.messages = list(map(ChatMessage, event_data['messages']))


class ChatEstablishedEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.work_target_id = event_data['workTargetId']
        self.messages = list(map(ChatMessage, event_data['messages']))


class ConversationMessageEvent(PollingEvent):
    def __init__(self, event_data: Dict[str, Any]):
        self.text: str = event_data.get('text')
        self.attachments = event_data.get('attachments')
        self.work_id = event_data['workId']


class EventType(ReverseLookupEnum):
    LoginResult = ("Agent/LoginResult", LoginResultEvent)
    WorkAssigned = ("Presence/WorkAssigned", WorkAssignedEvent)
    PresenceStatusChanged = ("Presence/PresenceStatusChanged", PresenceStatusChangedEvent)
    AsyncResult = ("AsyncResult", AsyncResultEvent)
    WorkAccepted = ("Presence/WorkAccepted", WorkAcceptedEvent)
    ChatRequest = ("LmAgent/ChatRequest", ChatRequestEvent)
    ChatEstablished = ("LmAgent/ChatEstablished", ChatEstablishedEvent)
    ConversationMessage = ("Conversational/ConversationMessage", ConversationMessageEvent)

    @classmethod
    def find_type(cls, value: str) -> Optional['EventType']:
        return cls._value_of(value)

    @classmethod
    def value_for_enum(cls, v: Tuple[str, Callable]) -> Any:
        return v[0]


class EventListener(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def process(self, event: PollingEvent):
        raise NotImplementedError()
