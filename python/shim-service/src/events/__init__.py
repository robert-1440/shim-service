import json
from typing import Optional, Union, Dict, Any

from events.event_types import EventType
from utils.date_utils import EpochMilliseconds, get_system_time_in_millis


class Event:
    def __init__(self,
                 tenant_id: int,
                 seq_no: int,
                 event_type: EventType,
                 event_id: str,
                 data: Optional[Union[str, dict]],
                 created_time: EpochMilliseconds = None):
        self.tenant_id = tenant_id
        self.seq_no = seq_no
        self.event_type = event_type
        self.event_id = event_id
        if data is not None and isinstance(data, dict):
            self.data_record = data
            data = json.dumps(data)
        else:
            self.data_record = None
        self.event_data = data
        if created_time is None:
            created_time = get_system_time_in_millis()
        self.created_time = created_time
        self.__record: Optional[Dict[str, Any]] = None

    def to_record(self) -> Dict[str, Any]:
        return {
            'tenantId': self.tenant_id,
            'seqNo': self.seq_no,
            'eventType': self.event_type.value,
            'eventId': self.event_id,
            'createdTime': self.created_time,
            'eventData': self.event_data
        }

    def __eq__(self, other):
        return (isinstance(other, Event) and
                self.tenant_id == other.tenant_id and
                self.seq_no == other.seq_no and
                self.event_type == other.event_type and
                self.event_id == other.event_id and
                self.event_data == other.event_data and
                self.created_time == other.created_time)

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return Event(
            record['tenantId'],
            record['seqNo'],
            EventType.value_of(record['eventType']),
            record['eventId'],
            record.get('eventData'),
            created_time=record['createdTime']
        )

    def get_event_key(self, key: str) -> Optional[Any]:
        if self.__record is None:
            self.__record = json.loads(self.event_data)
        return self.__record.get(key)
