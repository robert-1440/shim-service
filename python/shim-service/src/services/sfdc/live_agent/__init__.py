import json
import pickle
from enum import Enum
from typing import Dict, Any, Optional, List

from repos import Serializable
from services.sfdc.live_agent.message_data import MessageData
from utils import collection_utils
from utils.dict_utils import set_if_not_none
from utils.http_client import RequestBuilder

API_VERSION = 58
API_VERSION_STRING = str(API_VERSION)


class StatusOption(Enum):
    ONLINE = "online"
    BUSY = "busy"
    OFFLINE = "offline"


class PresenceStatus:
    def __init__(self, id: str, label: str, status_option: StatusOption):
        self.id = id
        self.label = label
        self.status_option = status_option

    def to_record(self) -> Dict[str, Any]:
        return {
            'id': self.id,
            'label': self.label,
            'statusOption': self.status_option.value
        }

    def __str__(self):
        return json.dumps(self.to_record(), indent=True)

    def __repr__(self):
        return self.__str__()


class LiveAgentStatus:
    def __init__(self, id: str, label: str, css_class: Optional[str], has_channels: bool, is_offline: bool):
        self.id = id
        self.label = label
        self.css_class = css_class
        self.has_channels = has_channels
        self.is_offline = is_offline

    @classmethod
    def from_record(cls, record):
        return cls(
            id=record['id'],
            label=record['label'],
            css_class=record.get('cssClass'),
            has_channels=record['hasChannels'],
            is_offline=record['isOffline']
        )

    def to_record(self) -> dict:
        record = {
            'id': self.id,
            'label': self.label,
            'hasChannels': self.has_channels,
            'isOffline': self.is_offline
        }
        set_if_not_none(record, 'cssClass', self.css_class)
        return record

    def __eq__(self, other):
        if not isinstance(other, LiveAgentStatus):
            return False

        return (
                self.id == other.id and
                self.label == other.label and
                self.css_class == other.css_class and
                self.has_channels == other.has_channels and
                self.is_offline == other.is_offline
        )

    def to_presence_status(self) -> PresenceStatus:
        if self.is_offline:
            status_option = StatusOption.OFFLINE
        elif self.has_channels:
            status_option = StatusOption.ONLINE
        else:
            status_option = StatusOption.BUSY
        return PresenceStatus(
            self.id,
            self.label,
            status_option
        )


class LiveAgentSession:
    def __init__(self, key: str, id: str, client_poll_timeout: int, affinity_token: str):
        self.key = key
        self.id = id
        self.client_poll_timeout = client_poll_timeout
        self.affinity_token = affinity_token

    def to_record(self) -> Dict[str, Any]:
        return {
            'key': self.key,
            'id': self.id,
            'clientPollTimeout': self.client_poll_timeout,
            'affinityToken': self.affinity_token
        }

    def __eq__(self, other):
        return (
                isinstance(other, LiveAgentSession)
                and self.key == other.key
                and self.id == other.id
                and self.client_poll_timeout == other.client_poll_timeout
                and self.affinity_token == other.affinity_token
        )

    def add_headers(self, builder: RequestBuilder):
        builder.header('X-Liveagent-Affinity', self.affinity_token)
        builder.header('X-Liveagent-Api-Version', API_VERSION_STRING)  # Replace with the desired version
        builder.header('X-Liveagent-Session-Key', self.key)

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(
            key=record['key'],
            id=record['id'],
            client_poll_timeout=record['clientPollTimeout'],
            affinity_token=record['affinityToken']
        )


class LiveAgentWebSettings:
    def __init__(self):
        self.sequence = 1

    def add_headers(self, rb: RequestBuilder):
        rb.header('X-Liveagent-Sequence', self.sequence)
        self.sequence += 1

    def serialize(self) -> bytes:
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> 'LiveAgentWebSettings':
        return pickle.loads(data)

    def __eq__(self, other):
        return isinstance(other, LiveAgentWebSettings) and self.sequence == other.sequence


class LiveAgentPollerSettings(Serializable):
    def __init__(self):
        self.ack = -1
        self.pc = 0
        self.message_list: List[MessageData] = []

    def serialize(self) -> bytes:
        self.message_list = []
        return pickle.dumps(self)

    @classmethod
    def deserialize(cls, data: bytes) -> 'LiveAgentPollerSettings':
        return pickle.loads(data)

    def add_message_data(self, message_data: MessageData) -> List[MessageData]:
        results = []
        if message_data.matches_ack(self.ack):
            results.append(message_data)
            self.ack = message_data.sequence

            while len(self.message_list) > 0:
                message_data = collection_utils.find_first_match(self.message_list,
                                                                 lambda m: m.matches_ack(self.ack))
                if message_data is None:
                    break
                self.message_list.remove(message_data)
                results.append(message_data)
                self.ack = message_data.sequence
        else:
            results.append(message_data)

        return results
