import abc
import functools
import os
from enum import Enum
from typing import Any, TypeVar, Dict, Collection, Union, Optional, Iterable

from bean.profiles import WEB_PROFILE, LIVE_AGENT_PROCESSOR_PROFILE, PUBSUB_POLLER_PROFILE, PUSH_NOTIFIER_PROFILE, \
    ALL_PROFILES, NON_WEB_PROFILES, NON_PUSH_PROFILES, SCHEDULER_PROFILE, NON_SCHEDULER_PROFILES, TABLE_LISTENER_PROFILE
from constants import SQS_PUSH_NOTIFICATION_QUEUE_URL
from utils import exception_utils
from utils.code_utils import import_module_and_get_attribute
from utils.collection_utils import to_collection
from utils.enum_utils import NameLookupEnum

T = TypeVar("T")

from utils.supplier import Supplier, MemoizedSupplier

#
# Set this to True when testing
#
RESETTABLE = os.environ.get("AWS_LAMBDA_FUNCTION_NAME") is None


def set_resettable(value: bool):
    global RESETTABLE
    RESETTABLE = value


class InvocableBean(metaclass=abc.ABCMeta):
    bean_name: 'BeanName'

    @abc.abstractmethod
    def invoke(self, parameters: Dict[str, Any]):
        raise NotImplementedError()


class BeanType(Enum):
    PUSH_NOTIFIER = 0x01
    EVENT_LISTENER = 0x02
    REQUEST_HANDLER = 0x04


HTTP_CLIENT_PROFILES = ALL_PROFILES ^ SCHEDULER_PROFILE ^ TABLE_LISTENER_PROFILE
INSTANCE_PROFILES = ALL_PROFILES ^ SCHEDULER_PROFILE ^ TABLE_LISTENER_PROFILE
EVENTS_PROFILES = ALL_PROFILES ^ SCHEDULER_PROFILE ^ TABLE_LISTENER_PROFILE
LAMBDA_PROFILES = ALL_PROFILES ^ SCHEDULER_PROFILE ^ TABLE_LISTENER_PROFILE


class BeanName(NameLookupEnum):
    SECRETS_MANAGER_CLIENT = 0, WEB_PROFILE
    HTTP_CLIENT = 1, HTTP_CLIENT_PROFILES
    DYNAMODB_CLIENT = 2, ALL_PROFILES
    DYNAMODB = 3, ALL_PROFILES
    INSTANCE = 4, INSTANCE_PROFILES
    SECRETS_REPO = 5, WEB_PROFILE
    EVENTS_REPO = 6, EVENTS_PROFILES
    ADMIN_CLIENT = 7, WEB_PROFILE
    AUTHENTICATOR = 8, WEB_PROFILE
    WEB_ROUTER = 9, WEB_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    SESSIONS_REPO = 10, ALL_PROFILES
    USER_SESSIONS_REPO = 11, ALL_PROFILES
    RESOURCE_LOCK_REPO = 12, ALL_PROFILES
    SNS_CLIENT = 13, ALL_PROFILES
    SNS = 14, ALL_PROFILES
    ERROR_NOTIFIER = 15, ALL_PROFILES
    CONFIG = 16, ALL_PROFILES
    HTTP_CLIENT_BUILDER = 17, HTTP_CLIENT_PROFILES
    PUSH_NOTIFICATION_CREDS = 18, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    FIREBASE_ADMIN = 19, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    PUSH_NOTIFICATION_CERT_BUILDER = 20, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    PUSH_NOTIFIER = 21, WEB_PROFILE | PUSH_NOTIFIER_PROFILE, {'type': BeanType.PUSH_NOTIFIER}
    SEQUENCE_REPO = 22, EVENTS_PROFILES
    SESSION_CONTEXTS_REPO = 23, ALL_PROFILES
    PUSH_NOTIFICATION_REPO = 24, NON_WEB_PROFILES ^ SCHEDULER_PROFILE ^ TABLE_LISTENER_PROFILE
    LIVE_AGENT_POLLER_PLATFORM = 25, WEB_PROFILE | LIVE_AGENT_PROCESSOR_PROFILE
    SFDC_SESSIONS_REPO = 26, ALL_PROFILES
    LAMBDA_INVOKER = 27, LAMBDA_PROFILES
    SESSION_CONNECTOR = 28, WEB_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    LAMBDA_CLIENT = 29, LAMBDA_PROFILES
    LIVE_AGENT_PROCESSOR = 30, LIVE_AGENT_PROCESSOR_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    SFDC_PUBSUB_POLLER = 31, PUBSUB_POLLER_PROFILE
    SQS_CLIENT = 32, EVENTS_PROFILES
    SCHEDULER = 33, EVENTS_PROFILES
    LIVE_AGENT_MESSAGE_DISPATCHER = 34, LIVE_AGENT_PROCESSOR_PROFILE
    PENDING_EVENTS_REPO = 35, EVENTS_PROFILES
    PUSH_NOTIFIER_PROCESSOR = 36, PUSH_NOTIFIER_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    SQS_PUSH_NOTIFIER = 37, WEB_PROFILE | PUSH_NOTIFIER_PROFILE, {'type': BeanType.PUSH_NOTIFIER,
                                                                  'var': SQS_PUSH_NOTIFICATION_QUEUE_URL}
    PUSH_NOTIFICATION_MANAGER = 38, WEB_PROFILE | PUSH_NOTIFIER_PROFILE
    WORK_ID_MAP_REPO = 39, WEB_PROFILE, {'type': BeanType.EVENT_LISTENER}
    SCHEDULER_CLIENT = 40, EVENTS_PROFILES
    LAMBDA_SCHEDULER_PROCESSOR = 41, SCHEDULER_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    TABLE_LISTENER_PROCESSOR = 42, TABLE_LISTENER_PROFILE, {'type': BeanType.REQUEST_HANDLER}
    PENDING_TENANT_EVENTS_REPO = 43, TABLE_LISTENER_PROFILE | PUBSUB_POLLER_PROFILE
    PUBSUB_POLLER_PROCESSOR = 44, PUBSUB_POLLER_PROFILE, {'type': BeanType.REQUEST_HANDLER}


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


class BeanRegistry(metaclass=abc.ABCMeta):

    def find_bean_by_name(self, name: str) -> Optional[Bean]:
        bean_name = BeanName._value_of(name, "Bean")
        return self.find_bean(bean_name)

    def get_bean_by_name(self, name: str) -> Bean:
        bean = self.find_bean_by_name(name)
        if bean is None:
            raise ValueError(f"No bean with name '{name}' found.")
        return bean

    @abc.abstractmethod
    def find_bean(self, bean_name: BeanName) -> Optional[Bean]:
        raise NotImplementedError()

    def get_bean(self, bean_name: BeanName) -> Bean:
        bean = self.find_bean(bean_name)
        if bean is None:
            raise BeanInitializationException(bean_name, f"No bean registered for {bean_name.name}.")
        return bean

    @abc.abstractmethod
    def get_beans_with_matching_type(self, bean_type: BeanType) -> Iterable[Bean]:
        raise NotImplementedError()


registry_supplier: Supplier[BeanRegistry] = MemoizedSupplier(lambda:
                                                             import_module_and_get_attribute("beans",
                                                                                             "registry",
                                                                                             from_module="bean"))


def inject(bean_instances: Union[BeanName, Collection[BeanName]] = None,
           beans: Union[BeanName, Collection[BeanName]] = None,
           bean_types: Union[BeanType, Collection[BeanType]] = None):
    """
    Used to inject bean instances or beans into a function call. They will be added to the end of the argument list,
    in the specified order (starting with instances then beans)
    :param bean_instances: bean instances to inject.
    :param beans: beans to inject
    :param bean_types: bean types to inject instances for
    """
    bean_instances = to_collection(bean_instances)
    beans = to_collection(beans)
    bean_types = to_collection(bean_types)
    if bean_instances is not None and len(bean_instances) == 0:
        bean_instances = None
    if beans is not None and len(beans) == 0:
        beans = None

    def load_bean_args():
        registry = registry_supplier.get()
        bean_args = []
        if bean_instances is not None:
            for bv in bean_instances:
                bean_args.append(get_bean_instance(bv))
        if bean_types is not None:
            for bv in bean_types:
                bean_list = registry.get_beans_with_matching_type(bv)
                bean_args.append(tuple(map(lambda b: b.get_instance(), bean_list)))
        if beans is not None:
            for bv in beans:
                bean_args.append(registry_supplier.get().get_bean(bv))
        return bean_args

    if RESETTABLE:
        loader = load_bean_args
    else:
        supplier = MemoizedSupplier(load_bean_args)
        loader = supplier.get

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args):
            args_copy = list(args)
            args_to_copy = loader()
            args_copy.extend(args_to_copy)
            return wrapped_function(*args_copy)

        return _inner_wrapper

    return decorator


def invoke_bean_by_name(name: str, parameters: Dict[str, Any]) -> Any:
    b: InvocableBean = registry_supplier.get().get_bean_by_name(name).get_instance()
    return b.invoke(parameters)


def get_bean_instance(name: BeanName) -> Any:
    return registry_supplier.get().get_bean(name).get_instance()


def get_invocable_bean(name: BeanName) -> InvocableBean:
    v = get_bean_instance(name)
    assert isinstance(v, InvocableBean)
    return v


def is_resettable() -> bool:
    return RESETTABLE
