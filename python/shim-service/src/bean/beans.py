import os
from threading import RLock
from typing import Union, Callable, Any, Dict, Collection, Optional, Iterable

import boto3

from bean import BeanName, Bean, BeanInitializationException, profiles, BeanRegistry, BeanType, \
    get_bean_instance, is_resettable, InvocableBean
from bean.profiles import get_active_profiles
from config import Config
from utils import exception_utils
from utils.code_utils import import_module_and_get_attribute

BeanValue = Union[Callable, Any]

_GLOBAL_MUTEX = RLock()


class _Boto3Loader:
    def __init__(self, service: str):
        self.service = service

    def invoke(self) -> Any:
        return boto3.client(self.service)


class _LazyLoader:
    def __init__(self, name: str,
                 bean_names: Union[Collection[BeanName], BeanName] = None):
        if bean_names is not None and isinstance(bean_names, BeanName):
            bean_names = (bean_names,)
        self.name = name
        self.bean_names = bean_names
        self.init_function = None

    def invoke(self, preload: bool = False) -> Any:
        if self.init_function is None:
            self.init_function = import_module_and_get_attribute(
                self.name,
                "init",
                "bean.loaders"
            )

        if self.bean_names is not None and len(self.bean_names) > 0:
            args = list(map(lambda n: get_bean_instance(n), self.bean_names))
        else:
            args = []
        return self.init_function(*args) if not preload else None


class _BeanImpl(Bean):
    def __init__(self, initializer: BeanValue):
        self.name: Optional[BeanName] = None
        self.__initializer = initializer
        self.__override_initializer = None
        self.__initialized = False
        self.__value = None
        self.__mutex = None
        self.__lazy = isinstance(initializer, _LazyLoader)
        self.__init_in_progress = False
        self.__bean_type_flags = 0
        self.__disabled = False

    def has_bean_type_flags(self, flags: int) -> bool:
        return not self.__disabled and (self.__bean_type_flags & flags) != 0

    def _set_name(self, name: BeanName):
        self.name = name
        if not is_resettable():
            profile_bits = name.value[1]
            if get_active_profiles() & profile_bits == 0:
                self.__disabled = True

        if len(name.value) > 2:
            params: dict = name.value[2]
            bt = params.get('type')
            if bt is not None:
                if type(bt) is tuple:
                    self.__bean_type_flags = 0
                    for b in bt:
                        self.__bean_type_flags |= b.value
                else:
                    self.__bean_type_flags = bt.value
            if not profiles.should_ignore_vars():
                env_var = params.get('var')
                if env_var is not None:
                    if len(os.environ.get(env_var, '')) == 0:
                        self.__disabled = True

        if not self.__disabled:
            if isinstance(self.__initializer, _LazyLoader):
                if self.__initializer.name is None:
                    self.__initializer.name = name.name.lower()

    def __execute_with_lock(self, caller: Callable):
        m = self.__mutex
        if m is None:
            with _GLOBAL_MUTEX:
                if self.__mutex is None:
                    if self.__initialized:
                        return
                    self.__mutex = RLock()
                m = self.__mutex
        with m:
            if self.__mutex is not None:
                caller()
                if not is_resettable():
                    self.__mutex = None

    def _preload(self):
        if self.__lazy:
            self.__initializer.invoke(True)

    def __initialize(self):
        assert not self.__init_in_progress, f"Bean initialization already in progress for {self.name}"
        self.__init_in_progress = True
        try:
            if self.__disabled:
                raise Exception(f"Bean {self.name} not active based on current profile.")
            initializer = self.__override_initializer if self.__override_initializer else self.__initializer
            if isinstance(initializer, _LazyLoader):
                self.__value = initializer.invoke()
            elif isinstance(initializer, _Boto3Loader):
                self.__value = initializer.invoke()
            elif callable(initializer):
                self.__value = initializer()
            else:
                self.__value = initializer
            if self.__bean_type_flags != 0 and isinstance(self.__value, InvocableBean):
                self.__value.bean_name = self.name
            self.__initialized = True
            return
        except BaseException as ex:
            exception_utils.print_exception(ex)
            ex_to_raise = BeanInitializationException(self.name)
        finally:
            self.__init_in_progress = False
        raise ex_to_raise

    def is_active(self, bits: int):
        return not self.__disabled

    def set_initializer(self, value: Any):
        self.__override_initializer = value
        self.__initialized = False

    @property
    def lazy(self):
        return self.__lazy

    def reset(self):
        assert is_resettable()
        if self.__initialized:
            self.__value = None
            self.__initialized = False
            self.__override_initializer = None
        self.__disabled = False

    def get_instance(self):
        if not self.__initialized:
            def init():
                if not self.__initialized:
                    self.__initialize()

            self.__execute_with_lock(init)
        return self.__value


def _module(name: str = None) -> _BeanImpl:
    return _BeanImpl(_LazyLoader(name))


def _boto3(name: str) -> _BeanImpl:
    return _BeanImpl(_Boto3Loader(name))


_BEANS: Dict[BeanName, _BeanImpl] = {
    BeanName.SECRETS_MANAGER_CLIENT: _boto3('secretsmanager'),
    BeanName.DYNAMODB_CLIENT: _boto3('dynamodb'),
    BeanName.HTTP_CLIENT: _module(),
    BeanName.INSTANCE: _module(),
    BeanName.SECRETS_REPO: _module(),
    BeanName.ADMIN_CLIENT: _module(),
    BeanName.AUTHENTICATOR: _module(),
    BeanName.WEB_ROUTER: _module('web'),
    BeanName.DYNAMODB: _module(),
    BeanName.SESSIONS_REPO: _module(),
    BeanName.USER_SESSIONS_REPO: _module(),
    BeanName.SNS_CLIENT: _boto3('sns'),
    BeanName.SNS: _module(),
    BeanName.ERROR_NOTIFIER: _module(),
    BeanName.CONFIG: _BeanImpl(lambda: Config()),
    BeanName.HTTP_CLIENT_BUILDER: _module(),
    BeanName.PUSH_NOTIFICATION_CREDS: _module('push_provider_creds'),
    BeanName.PUSH_NOTIFICATION_CERT_BUILDER: _module('push_cert_builder'),
    BeanName.PUSH_NOTIFICATION_REPO: _module(),
    BeanName.FIREBASE_ADMIN: _module('firebase'),
    BeanName.PUSH_NOTIFIER: _module(),
    BeanName.SEQUENCE_REPO: _module(),
    BeanName.EVENTS_REPO: _module(),
    BeanName.SFDC_SESSIONS_REPO: _module(),
    BeanName.LIVE_AGENT_POLLER_PLATFORM: _module(),
    BeanName.SESSION_CONTEXTS_REPO: _module(),
    BeanName.LAMBDA_CLIENT: _boto3('lambda'),
    BeanName.LAMBDA_INVOKER: _module(),
    BeanName.SESSION_CONNECTOR: _module(),
    BeanName.RESOURCE_LOCK_REPO: _module(),
    BeanName.LIVE_AGENT_PROCESSOR: _module(),
    BeanName.SCHEDULER_CLIENT: _boto3('scheduler'),
    BeanName.SCHEDULER: _module(),
    BeanName.LIVE_AGENT_MESSAGE_DISPATCHER: _module(),
    BeanName.PENDING_EVENTS_REPO: _module(),
    BeanName.PUSH_NOTIFIER_PROCESSOR: _module(),
    BeanName.PUSH_NOTIFICATION_MANAGER: _module(),
    BeanName.SQS_PUSH_NOTIFIER: _module(),
    BeanName.WORK_ID_MAP_REPO: _module(),
    BeanName.SQS_CLIENT: _boto3('sqs'),
    BeanName.LAMBDA_SCHEDULER_PROCESSOR: _module(),
    BeanName.TABLE_LISTENER_PROCESSOR: _module()
}


def __setup_beans():
    for name, value in _BEANS.items():
        value._set_name(name)


__setup_beans()


def override_bean(name: BeanName, value: BeanValue):
    """
    This should be used for testing only.

    :param name: the bean name.
    :param value: the value for the bean.
    """
    assert isinstance(name, BeanName)
    b = _BEANS[name]
    b.set_initializer(value)


def reset():
    assert is_resettable()
    setattr(profiles, "_active_profiles", None)
    """
    Use during unit tests only!
    """
    for bean in _BEANS.values():
        bean.reset()
    __setup_beans()


def load_all_lazy():
    """
    Used to load all the lazy beans.  This should be called when archiving only.
    """
    impl: _BeanImpl
    profile_bits = get_active_profiles()
    for impl in filter(lambda b: b.lazy and b.is_active(profile_bits), _BEANS.values()):
        impl._preload()


class RegistryImpl(BeanRegistry):

    def find_bean(self, bean_name: BeanName) -> Optional[Bean]:
        return _BEANS.get(bean_name)

    def get_beans_with_matching_type(self, bean_type: BeanType) -> Iterable[Bean]:
        return filter(lambda b: b.has_bean_type_flags(bean_type.value), _BEANS.values())


registry = RegistryImpl()
