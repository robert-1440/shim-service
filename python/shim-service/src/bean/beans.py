import functools
import os
import sys
from functools import reduce
from threading import RLock
from traceback import print_exc
from typing import Union, Callable, Any, Dict, Collection, Optional

import boto3

from bean import BeanName, Bean, BeanInitializationException, profiles, InvocableBean, BeanType
from bean.profiles import get_active_profiles
from config import Config

BeanValue = Union[Callable, Any]

#
# Set this to True when testing
#
RESETTABLE = False

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
            code = f"from bean.loaders import {self.name}\n\n"
            local_vars = {}
            exec(code, sys.modules[__name__].__dict__, local_vars)
            self.init_function = local_vars[self.name].__dict__['init']

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
        if not RESETTABLE:
            profile_bits = name.value[1]
            if get_active_profiles() & profile_bits == 0:
                self.__disabled = True

        if len(name.value) > 2:
            params: dict = name.value[2]
            bt = params.get('type')
            if bt is not None:
                self.__bean_type_flags = bt.value
            env_var = params.get('var')
            if env_var is not None:
                if len(os.environ.get(env_var, '')) == 0:
                    self.__disabled = True

        if not self.__disabled:
            if isinstance(self.__initializer, _LazyLoader):
                if self.__initializer.name is None:
                    self.__initializer.name = name.name.lower()

    def __execute_with_lock(self, caller: Callable):
        if self.__mutex is None:
            with _GLOBAL_MUTEX:
                if self.__mutex is None:
                    self.__mutex = RLock()
        try:
            with self.__mutex:
                caller()
        finally:
            if not RESETTABLE:
                del self.__mutex

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
            self.__initialized = True
            return
        except Exception as ex:
            print_exc()
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
        assert RESETTABLE
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


__BEANS: Dict[BeanName, _BeanImpl] = {
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
    BeanName.SNS_PUSH_NOTIFIER: _module(),
    BeanName.WORK_ID_MAP_REPO: _module()
}


def __setup_beans():
    for name, value in __BEANS.items():
        value._set_name(name)


__setup_beans()


def __get_bean_by_name(name: str) -> Bean:
    for b in __BEANS.values():
        if b.name.name == name:
            return b
    raise ValueError(f"Bean with name '{name}' not found.")


def override_bean(name: BeanName, value: BeanValue):
    """
    This should be used for testing only.

    :param name: the bean name.
    :param value: the value for the bean.
    """
    assert isinstance(name, BeanName)
    b = __BEANS[name]
    b.set_initializer(value)


def reset():
    assert RESETTABLE
    setattr(profiles, "_active_profiles", None)
    """
    Use during unit tests only!
    """
    for bean in __BEANS.values():
        bean.reset()
    __setup_beans()


def get_bean(name: BeanName) -> Bean:
    return __BEANS[name]


def get_bean_instance(name: BeanName) -> Any:
    b = __BEANS.get(name)
    if b is None:
        raise BeanInitializationException(name, f"No bean registered for {name.name}")
    return b.get_instance()


def get_invocable_bean(name: BeanName) -> InvocableBean:
    v = get_bean_instance(name)
    assert isinstance(v, InvocableBean)
    return v


def _to_collection(thing: Any):
    if thing is not None:
        if not isinstance(thing, Collection):
            return (thing,)
        if len(thing) == 0:
            return None
    return thing


def _get_beans_by_type(flags: int):
    pass


def _get_bean_type_flags(bean_types: Collection[BeanType]):
    def reducer(a, b):
        return a | b

    return reduce(reducer, map(lambda b: b.value, bean_types), 0)


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
    bean_instances = _to_collection(bean_instances)
    beans = _to_collection(beans)
    bean_types = _to_collection(bean_types)
    if bean_instances is not None and len(bean_instances) == 0:
        bean_instances = None
    if beans is not None and len(beans) == 0:
        beans = None

    bean_args = None

    def load_bean_args(args_copy: list):
        nonlocal bean_args
        if bean_args is None or RESETTABLE:
            bean_args = []
            if bean_instances is not None:
                for bv in bean_instances:
                    bean_args.append(get_bean_instance(bv))
            if bean_types is not None:
                for bv in bean_types:
                    flags = _get_bean_type_flags(_to_collection(bv))
                    bean_list = map(lambda b: b.get_instance(),
                                    filter(lambda b: b.has_bean_type_flags(flags), __BEANS.values()))
                    bean_args.append(tuple(bean_list))
            if beans is not None:
                for bv in beans:
                    bean_args.append(get_bean(bv))
        args_copy.extend(bean_args)

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args):
            args_copy = list(args)
            load_bean_args(args_copy)
            return wrapped_function(*args_copy)

        return _inner_wrapper

    return decorator


def load_all_lazy():
    """
    Used to load all the lazy beans.  This should be called when archiving only.
    """
    impl: _BeanImpl
    profile_bits = get_active_profiles()
    for impl in filter(lambda b: b.lazy and b.is_active(profile_bits), __BEANS.values()):
        impl._preload()


def invoke_bean_by_name(name: str, parameters: Dict[str, Any]) -> Any:
    b: InvocableBean = __get_bean_by_name(name).get_instance()
    return b.invoke(parameters)
