from enum import Enum
from enum import Enum
from typing import Dict, Any, Tuple, Optional

from utils.date_utils import EpochMilliseconds, get_system_time_in_millis
from utils.enum_utils import ReverseLookupEnum


class TenantContextType(ReverseLookupEnum):
    X1440 = 'X'

    @classmethod
    def value_of(cls, c: str) -> 'TenantContextType':
        return cls._value_of(c, "Tenant context type")


TenantAndSessionCount = Tuple[int, int]


class PendingTenantEventType(Enum):
    X1440_POLL = "x1440"

    @classmethod
    def value_of(cls, value: str) -> 'PendingTenantEventType':
        if value == 'x1440':
            return PendingTenantEventType.X1440_POLL
        raise ValueError(f"Invalid pending tenant event type: {value}.")


class PendingTenantEvent:
    def __init__(self,
                 event_type: PendingTenantEventType,
                 org_id: str,
                 tenant_id: int,
                 access_token: str,
                 instance_url: str,
                 event_time: Optional[EpochMilliseconds] = None,
                 active_at: Optional[EpochMilliseconds] = None,
                 state_counter: int = 0,
                 ):
        self.event_type = event_type
        self.org_id = org_id
        self.tenant_id = tenant_id
        self.access_token = access_token
        self.instance_url = instance_url
        self.event_time = event_time or get_system_time_in_millis()
        self.active_at = active_at or self.event_time
        self.state_counter = state_counter

    def to_record(self) -> Dict[str, Any]:
        return {
            'eventType': self.event_type.value,
            'orgId': self.org_id,
            'tenantId': self.tenant_id,
            'accessToken': self.access_token,
            'instanceUrl': self.instance_url,
            'eventTime': self.event_time,
            'activeAt': self.active_at,
            'stateCounter': self.state_counter
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'PendingTenantEvent':
        return cls(
            PendingTenantEventType.value_of(record['eventType']),
            record['orgId'],
            record['tenantId'],
            record['sessionCount'],
            record['accessToken'],
            record['instanceUrl'],
            record['eventTime'],
            record['activeAt']
        )


class TenantContext:

    def __init__(self, context_type: TenantContextType, tenant_id: int, state_counter: int, data: bytes):
        self.context_type = context_type
        self.tenant_id = tenant_id
        self.state_counter = state_counter
        self.data = data

    def to_record(self) -> Dict[str, Any]:
        return {
            'contextType': self.context_type.value,
            'tenantId': self.tenant_id,
            'stateCounter': self.state_counter,
            'contextData': self.data
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(
            TenantContextType.value_of(record['contextType']),
            record['tenantId'],
            record['stateCounter'],
            record['contextData']
        )
