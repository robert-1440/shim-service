import abc
from enum import Enum
from typing import Any, TypeVar, Dict

from bean.profiles import WEB_PROFILE, LIVE_AGENT_PROCESSOR_PROFILE, PUBSUB_POLLER_PROFILE, PUSH_NOTIFIER_PROFILE, \
    ALL_PROFILES, NON_WEB_PROFILES, NON_PUSH_PROFILES
from utils import exception_utils

T = TypeVar("T")

from utils.supplier import Supplier, MemoizedSupplier


class InvocableBean(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def invoke(self, parameters: Dict[str, Any]):
        raise NotImplementedError()


class BeanType(Enum):
    PUSH_NOTIFIER = 0x01


class BeanName(Enum):
    SECRETS_MANAGER_CLIENT = 0, WEB_PROFILE
    HTTP_CLIENT = 1, ALL_PROFILES
    DYNAMODB_CLIENT = 2, ALL_PROFILES
    DYNAMODB = 3, ALL_PROFILES
    INSTANCE = 4, ALL_PROFILES
    SECRETS_REPO = 5, WEB_PROFILE
    EVENTS_REPO = 6, ALL_PROFILES
    ADMIN_CLIENT = 7, ALL_PROFILES
    AUTHENTICATOR = 8, WEB_PROFILE
    WEB_ROUTER = 9, WEB_PROFILE
    SESSIONS_REPO = 10, ALL_PROFILES
    USER_SESSIONS_REPO = 11, ALL_PROFILES
    RESOURCE_LOCK_REPO = 12, ALL_PROFILES
    SNS_CLIENT = 13, ALL_PROFILES
    SNS = 14, ALL_PROFILES
    ERROR_NOTIFIER = 15, ALL_PROFILES
    CONFIG = 16, ALL_PROFILES
    HTTP_CLIENT_BUILDER = 17, ALL_PROFILES
    PUSH_NOTIFICATION_CREDS = 18, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    FIREBASE_ADMIN = 19, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    PUSH_NOTIFICATION_CERT_BUILDER = 20, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    PUSH_NOTIFIER = 21, WEB_PROFILE | PUSH_NOTIFIER_PROFILE, {'type': BeanType.PUSH_NOTIFIER}
    SEQUENCE_REPO = 22, ALL_PROFILES
    SESSION_CONTEXTS_REPO = 23, ALL_PROFILES
    PUSH_NOTIFICATION_REPO = 24, NON_WEB_PROFILES
    LIVE_AGENT_POLLER_PLATFORM = 25, WEB_PROFILE | LIVE_AGENT_PROCESSOR_PROFILE
    SFDC_SESSIONS_REPO = 26, NON_PUSH_PROFILES
    LAMBDA_INVOKER = 27, ALL_PROFILES
    SESSION_CONNECTOR = 28, WEB_PROFILE
    LAMBDA_CLIENT = 29, ALL_PROFILES
    LIVE_AGENT_PROCESSOR = 30, LIVE_AGENT_PROCESSOR_PROFILE
    SFDC_PUBSUB_POLLER = 31, PUBSUB_POLLER_PROFILE
    SCHEDULER_CLIENT = 32, ALL_PROFILES
    SCHEDULER = 33, ALL_PROFILES
    LIVE_AGENT_MESSAGE_DISPATCHER = 34, LIVE_AGENT_PROCESSOR_PROFILE
    PENDING_EVENTS_REPO = 35, ALL_PROFILES
    PUSH_NOTIFIER_PROCESSOR = 36, PUSH_NOTIFIER_PROFILE
    SNS_PUSH_NOTIFIER = 37, WEB_PROFILE | PUSH_NOTIFIER_PROFILE, {'type': BeanType.PUSH_NOTIFIER,
                                                                  'var': 'SNS_NOTIFIER_ENABLED'}
    PUSH_NOTIFICATION_MANAGER = 38, WEB_PROFILE | PUSH_NOTIFIER_PROFILE


BeanSupplier = Supplier[T]


class BeanInitializationException(Exception):
    def __init__(self, bean_name: BeanName, message: str = None):
        message = message if message is not None else exception_utils.dump_ex()

        super(BeanInitializationException, self).__init__(f"Initialization of bean '{bean_name.name}' "
                                                          f"failed: {message}")


class Bean(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_instance(self) -> Any:
        raise NotImplementedError()

    def create_supplier(self) -> BeanSupplier[T]:
        return MemoizedSupplier(self.get_instance)
