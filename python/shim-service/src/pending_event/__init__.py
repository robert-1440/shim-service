from enum import Enum
from typing import Optional, Dict, Any

from session import SessionKey
from utils.date_utils import EpochMilliseconds, get_system_time_in_millis


class PendingEventType(Enum):
    LIVE_AGENT_POLL = "lap"

    @classmethod
    def value_of(cls, value: str) -> 'PendingEventType':
        if value == 'lap':
            return PendingEventType.LIVE_AGENT_POLL
        raise ValueError(f"Invalid pending event type: {value}.")


class PendingEvent(SessionKey):
    def __init__(self,
                 event_type: PendingEventType,
                 tenant_id: int,
                 session_id: str,
                 user_id: Optional[str],
                 event_time: Optional[EpochMilliseconds] = None,
                 active_at: Optional[EpochMilliseconds] = None,
                 update_time: Optional[EpochMilliseconds] = None):
        self.event_type = event_type
        self.event_time = event_time or get_system_time_in_millis()
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.user_id = user_id
        self.active_at = active_at or self.event_time
        self.update_time = update_time or self.event_time

    def to_record(self) -> Dict[str, Any]:
        return {
            'eventType': self.event_type.value,
            'eventTime': self.event_time,
            'tenantId': self.tenant_id,
            'sessionId': self.session_id,
            'userId': self.user_id,
            'activeAt': self.active_at,
            'updateTime': self.update_time
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'PendingEvent':
        return cls(
            PendingEventType.value_of(record['eventType']),
            record['tenantId'],
            record['sessionId'],
            record.get('userId'),
            record['eventTime'],
            record['activeAt'],
            record.get('updateTime')
        )
