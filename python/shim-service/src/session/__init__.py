from enum import Enum
from traceback import print_exc
from typing import Optional, List, Any, Dict, Callable

from auth import Credentials
from lambda_web_framework.web_exceptions import NotAuthorizedException, ConflictException
from platform_channels import OMNI_PLATFORM, PlatformChannel, X1440_PLATFORM
from utils import loghelper
from utils.date_utils import EpochMilliseconds, get_system_time_in_millis, EpochSeconds
from utils.dict_utils import set_if_not_none
from utils.enum_utils import ReverseLookupEnum

logger = loghelper.get_logger(__name__)


class SessionStatus(Enum):
    PENDING = "P"
    ACTIVE = "A"
    FAILED = "F"


def _map_session_status(input_status: str) -> SessionStatus:
    if input_status == 'P':
        return SessionStatus.PENDING
    if input_status == 'A':
        return SessionStatus.ACTIVE
    if input_status == 'F':
        return SessionStatus.FAILED
    raise NotImplementedError(f"Invalid status: {input_status}")


class UserSession:
    def __init__(self,
                 tenant_id: int,
                 user_id: str,
                 session_id: str,
                 fcm_device_token: str,
                 time_created: EpochMilliseconds):
        self.tenant_id = tenant_id
        self.user_id = user_id
        self.session_id = session_id
        self.fcm_device_token = fcm_device_token
        self.time_created = time_created

    def to_record(self) -> Dict[str, Any]:
        return {
            'tenantId': self.tenant_id,
            'userId': self.user_id,
            'sessionId': self.session_id,
            'fcmDeviceToken': self.fcm_device_token,
            'timeCreated': self.time_created
        }

    def __eq__(self, other):
        if not isinstance(other, UserSession):
            return False
        return (self.tenant_id == other.tenant_id and
                self.user_id == other.user_id and
                self.session_id == other.session_id and
                self.fcm_device_token == other.fcm_device_token and
                self.time_created == other.time_created)

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return UserSession(
            record['tenantId'],
            record['userId'],
            record['sessionId'],
            record['fcmDeviceToken'],
            record['timeCreated']
        )


class SessionKey:
    tenant_id: int
    session_id: str

    def __str__(self):
        return f"{self.tenant_id}#{self.session_id}"

    def __repr__(self):
        return self.__str__()

    def to_logging_data(self) -> Dict[str, Any]:
        return {'session': f"{self.tenant_id}#{self.session_id}"}

    def execute_with_logging(self, caller: Callable) -> Any:
        return loghelper.execute_with_logging_info(self.to_logging_data(), caller)

    def to_key_dict(self) -> Dict[str, Any]:
        return {
            'tenantId': self.tenant_id,
            'sessionId': self.session_id
        }

    @classmethod
    def key_of(cls, tenant_id: int, session_id: str) -> 'SessionKey':
        v = SessionKey()
        v.tenant_id = tenant_id
        v.session_id = session_id
        return v

    @classmethod
    def key_from_dict(cls, record: Dict[str, Any]) -> 'SessionKey':
        return cls.key_of(record['tenantId'], record['sessionId'])


class SessionToken(SessionKey):
    def __init__(self, tenant_id: int, session_id: str, user_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id

    def serialize(self, creds: Credentials) -> str:
        token = f"e40~{self.tenant_id}~{self.session_id}~{self.user_id}"
        return creds.obfuscate_data(token)

    def __eq__(self, other):
        return isinstance(other, SessionToken) and \
            self.session_id == other.session_id and \
            self.tenant_id == other.tenant_id and \
            self.user_id == other.user_id

    @classmethod
    def deserialize(cls, creds: Credentials, token: str):
        try:
            data = creds.clarify_data(token)
            values = data.split('~')
            if len(values) == 4 and values[0] == 'e40':
                return SessionToken(int(values[1]), values[2], values[3])
            raise ValueError(f"Token '{token}' is invalid.")
        except Exception as ex:
            print_exc()
            logger.warning(f"Attempt to decrypt token failed: {ex}")

        raise NotAuthorizedException("Invalid session token.")


class Session(SessionKey):
    time_created: int
    update_time: int
    access_token: Optional[str]
    state_counter: int
    expiration_seconds: int
    fcm_device_token: Optional[str]
    instance_url: str
    user_id: str
    session_id: str
    tenant_id: int
    channel_platform_types: List[str]
    status: SessionStatus
    expiration_time: EpochSeconds

    def __init__(self, tenant_id: int,
                 session_id: str,
                 time_created: Optional[EpochMilliseconds],
                 user_id: str,
                 instance_url: str,
                 access_token: str,
                 fcm_device_token: Optional[str],
                 expiration_seconds: int,
                 channel_platform_types: List[str],
                 state_counter=1,
                 update_time: Optional[EpochMilliseconds] = None,
                 status: SessionStatus = SessionStatus.PENDING,
                 failure_message: str = None,
                 expiration_time: int = None):
        assert tenant_id is not None
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.time_created = time_created or get_system_time_in_millis()
        self.user_id = user_id
        self.instance_url = instance_url
        self.fcm_device_token = fcm_device_token
        self.expiration_seconds = expiration_seconds
        self.channel_platform_types = channel_platform_types
        self.state_counter = state_counter
        self.update_time = update_time or self.time_created
        self.access_token = access_token
        self.status = status
        self.failure_message = failure_message
        self.expiration_time = expiration_time

    def has_live_agent_polling(self) -> bool:
        return OMNI_PLATFORM.name in self.channel_platform_types

    def set_failed(self, message: str):
        self.status = SessionStatus.FAILED
        self.failure_message = message

    def describe(self):
        return f"tenant_id={self.tenant_id}, session_id={self.session_id}, user_id={self.user_id}"

    def can_replace_session(self, new_session: Any):
        """
        Whether this session can be replaced with the new one.

        :param new_session: the new session.
        :return: True if the session can be replaced.
        """
        new_session: Session
        return self.tenant_id == new_session.tenant_id and \
            self.user_id == new_session.user_id and \
            self.fcm_device_token == new_session.fcm_device_token

    def should_replace_session(self, new_session: Any):
        """
        Whether this session should be replaced with the new one.

        :param new_session: the new session.
        :return: True if this session should be replaced.
        """
        new_session: Session
        assert self.can_replace_session(new_session)
        return self.access_token != new_session.access_token

    def to_record(self):
        record = {
            'tenantId': self.tenant_id,
            'sessionId': self.session_id,
            'timeCreated': self.time_created,
            'userId': self.user_id,
            'instanceUrl': self.instance_url,
            'accessToken': self.access_token,
            'expirationSeconds': self.expiration_seconds,
            'platformTypes': self.channel_platform_types,
            'stateCounter': self.state_counter,
            'updateTime': self.update_time,
            'sessionStatus': self.status.value,
            'expireTime': self.expiration_time
        }
        set_if_not_none(record, 'fcmDeviceToken', self.fcm_device_token)
        set_if_not_none(record, 'failureMessage', self.failure_message)
        return record

    def to_user_session(self) -> UserSession:
        return UserSession(
            tenant_id=self.tenant_id,
            session_id=self.session_id,
            user_id=self.user_id,
            fcm_device_token=self.fcm_device_token,
            time_created=self.time_created
        )

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return Session(record['tenantId'], record['sessionId'], record['timeCreated'], record['userId'],
                       record['instanceUrl'], record['accessToken'], record.get('fcmDeviceToken'),
                       record['expirationSeconds'], record['platformTypes'], record['stateCounter'],
                       record['updateTime'],
                       _map_session_status(record['sessionStatus']),
                       record.get('failureMessage'),
                       record.get('expireTime'))

    def __eq__(self, other):
        if isinstance(other, Session):
            return (
                    self.time_created == other.time_created and
                    self.update_time == other.update_time and
                    self.access_token == other.access_token and
                    self.state_counter == other.state_counter and
                    self.expiration_seconds == other.expiration_seconds and
                    self.fcm_device_token == other.fcm_device_token and
                    self.instance_url == other.instance_url and
                    self.user_id == other.user_id and
                    self.session_id == other.session_id and
                    self.tenant_id == other.tenant_id and
                    self.channel_platform_types == other.channel_platform_types and
                    self.status == other.status

            )
        return False


def verify_session_status(session: Session, pending_ok: bool = False, allow_failure: bool = False):
    if session.status == SessionStatus.ACTIVE:
        return
    if session.status == SessionStatus.PENDING and not pending_ok:
        raise ConflictException("The session is in the process of being created.",
                                error_code="SessionCreationInProgress")
    if session.status == SessionStatus.FAILED and not allow_failure:
        raise ConflictException(f"The session is in a failed state: {session.failure_message}",
                                error_code="SessionInFailedState")


class ContextType(ReverseLookupEnum):
    WEB = 'W'
    LIVE_AGENT = 'L'
    X1440 = 'X'
    PUSH_NOTIFIER = 'P'

    def to_platform_channel(self) -> PlatformChannel:
        if self == ContextType.LIVE_AGENT:
            return OMNI_PLATFORM
        if self == ContextType.X1440:
            return X1440_PLATFORM
        raise ValueError(f"No platform for {self.value}")

    @classmethod
    def value_of(cls, string_value: str) -> 'ContextType':
        return cls._value_of(string_value, 'context type')


class SessionContext(SessionKey):
    def __init__(self,
                 tenant_id: int,
                 session_id: str,
                 user_id: str,
                 context_type: ContextType,
                 session_data: bytes):
        self.__tenant_id = tenant_id
        self.__session_id = session_id
        self.__user_id = user_id
        self.__context_type = context_type
        self.__data = session_data

    def to_record(self) -> Dict[str, Any]:
        return {
            "tenantId": self.__tenant_id,
            "sessionId": self.__session_id,
            "userId": self.__user_id,
            "contextType": self.__context_type.value,
            "sessionData": self.__data
        }

    @classmethod
    def from_record(cls, record: dict) -> 'SessionContext':
        return cls(
            record['tenantId'],
            record['sessionId'],
            record['userId'],
            ContextType.value_of(record['contextType']),
            record['sessionData']
        )

    @property
    def tenant_id(self) -> int:
        return self.__tenant_id

    @property
    def session_id(self) -> str:
        return self.__session_id

    @property
    def user_id(self) -> str:
        return self.__user_id

    @property
    def context_type(self) -> ContextType:
        return self.__context_type

    @property
    def session_data(self) -> bytes:
        return self.__data

    def set_session_data(self, data: bytes) -> 'SessionContext':
        if data == self.__data:
            return self
        return SessionContext(
            self.__tenant_id,
            self.__session_id,
            self.__user_id,
            self.__context_type,
            data
        )
