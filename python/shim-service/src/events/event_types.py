from utils.enum_utils import ReverseLookupEnum


class EventType(ReverseLookupEnum):
    SESSION_CREATED = 'SC'
    SESSION_ACTIVATED = 'SA'
    SESSION_UPDATED = 'SU'
    SESSION_TOUCHED = 'ST'
    SESSION_DELETED = 'SD'
    PUSH_NOTIFICATION = 'PN'
    PRESENCE_STATUS_SET = 'SS'
    WORK_ACCEPTED = 'WA'
    WORK_DECLINED = 'WD'
    WORK_CLOSED = 'WC'

    @classmethod
    def value_of(cls, string: str) -> 'EventType':
        return cls._value_of(string, "Event Type")
