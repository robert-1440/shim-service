import abc
import functools
from threading import RLock, Thread
from typing import Optional, Callable, Any, Tuple

from retry.api import retry_call

from bean import beans, BeanName
from bean.beans import inject
from lambda_pkg import LambdaFunction
from lambda_web_framework.web_exceptions import ConflictException
from repos import OptimisticLockException
from scheduler import Scheduler
from session import SessionKey
from utils import loghelper, exception_utils
from utils.signal_event import SignalEvent

logger = loghelper.get_logger(__name__)


class SessionLockedException(Exception):
    def __init__(self):
        super(SessionLockedException, self).__init__("Session locked.")


class ResourceLock(metaclass=abc.ABCMeta):
    name: str

    @abc.abstractmethod
    def refresh(self) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def release(self) -> bool:
        raise NotImplementedError()

    def execute_and_release_on_exception(self, caller: Callable):
        ok = False
        try:
            result = caller()
            ok = True
            return result
        finally:
            if not ok:
                self.release()

    def execute_and_release_on_false(self, caller: Callable[[], bool]) -> bool:
        result = self.execute_and_release_on_exception(caller)
        if not result:
            self.release()
        return result

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class AutoRefreshLock(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def release(self) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def check(self) -> bool:
        raise NotImplementedError()


class _AutoRefreshLockImpl(AutoRefreshLock):
    def __init__(self, source: ResourceLock, lock_timeout_seconds: int):
        self.mutex = RLock()
        self.source = source
        self.released: Optional[bool] = None
        self.thread = Thread(target=self.__worker, name=source.name)
        self.failed = False
        self.wait_time = (lock_timeout_seconds * 1000) - 500
        self.signal_event = SignalEvent(manual_reset=True)
        self.thread.start()

    def __worker(self):
        while not self.failed and not self.signal_event.wait(self.wait_time) and self.released is None:
            try:
                with self.mutex:
                    if self.released is not None:
                        break
                    if not self.source.refresh():
                        self.failed = True
            except BaseException as ex:
                logger.error(f"Failed to refresh resource {self.source.name}: {exception_utils.dump_ex(ex)}")
                self.failed = True

    def release(self) -> bool:
        if self.released is None:
            with self.mutex:
                self.released = self.source.release()

            self.signal_event.notify()
            self.thread.join(1)

        return self.released

    def check(self) -> bool:
        return not self.failed and self.released is None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class ResourceLockRepo(metaclass=abc.ABCMeta):

    def acquire(self,
                name: str,
                refresh_seconds: int,
                timeout_seconds: int) -> Optional[ResourceLock]:
        assert timeout_seconds > 0

        def local_try() -> ResourceLock:
            l = self.try_acquire(name, refresh_seconds)
            if l is None:
                raise OptimisticLockException()
            return l

        return retry_call(
            local_try,
            exceptions=OptimisticLockException,
            delay=timeout_seconds,
            max_delay=timeout_seconds,
            backoff=.1,
            jitter=(.1, .9)
        )

    def acquire_and_execute(self, name: str,
                            refresh_seconds: int,
                            timeout_seconds: int,
                            caller: Callable) -> Tuple[ResourceLock, Any]:
        lock = self.acquire(name, refresh_seconds, timeout_seconds)
        if lock is None:
            raise ConflictException("Unable to lock session")
        ok = False
        try:
            v = caller()
            ok = True
            return lock, v
        finally:
            if not ok:
                lock.release()

    def try_acquire_auto_refresh_lock(self, name: str, refresh_seconds: int,
                                      timeout_seconds: int = None) -> Optional[AutoRefreshLock]:
        """
        Used to acquire that will automatically refresh the lock every max_lock_time_seconds by starting
        a background thread. Take care with starting too many threads.

        :param name: the name of the resource.
        :param refresh_seconds: the interval for refreshing the lock.
        :param timeout_seconds: if not None, wait the given number of seconds to acquire the lock
        :return: an AutoRefreshLock if the lock was acquired, otherwise None.
        """
        if timeout_seconds is not None and timeout_seconds > 0:
            lock = self.acquire(name, refresh_seconds, timeout_seconds)
        else:
            lock = self.try_acquire(name, refresh_seconds)
        return _AutoRefreshLockImpl(lock, max(1, refresh_seconds - 2)) if lock is not None else None

    @abc.abstractmethod
    def try_acquire(self, name: str, expire_seconds: int) -> Optional[ResourceLock]:
        raise NotImplementedError()


@inject(bean_instances=BeanName.SCHEDULER)
def __schedule_lambda(lock_type: str,
                      key: SessionKey,
                      function: LambdaFunction,
                      minutes: Optional[int],
                      scheduler: Scheduler):
    if minutes is None:
        minutes = 1
    name = f"l-{lock_type}-{key.tenant_id}-{key.session_id}"
    event = key.to_key_dict()
    event['fromSchedule'] = True
    scheduler.schedule_lambda_minutes(
        name,
        minutes,
        function,
        event
    )


def __attempt_session_lock(
        lock_type: str,
        locker: Callable[[ResourceLockRepo, str], Any],
        lambda_function: Optional[LambdaFunction],
        schedule_minutes: Optional[int],
        caller: Callable,
        *args):
    key: SessionKey = args[0]
    if not isinstance(key, SessionKey):
        # Might be an instance method
        key = args[1]
        assert isinstance(key, SessionKey)

    name = f"{lock_type}/{key.tenant_id}/{key.session_id}"

    lock = locker(beans.get_bean_instance(BeanName.RESOURCE_LOCK_REPO), name)
    if lock is None:
        if lambda_function is not None:
            __schedule_lambda(
                lock_type,
                key,
                lambda_function,
                schedule_minutes
            )
        raise SessionLockedException()
    with lock:
        return caller(*args)


def session_auto_lock(lock_type: str,
                      timeout_seconds: int,
                      refresh_seconds: int,
                      lambda_function: Optional[LambdaFunction] = None,
                      schedule_minutes: int = None):
    """
    Use this to decorate functions that want exclusive access to a session by obtaining an auto refresh lock.
    The first argument of the function must be a SessionKey.

    :param lock_type: the lock type name used when forming the lock name. It will be of the form {lock_type}/tenant_id/session_id
    :param timeout_seconds: the number of seconds to wait when obtaining the lock.
    :param refresh_seconds: the lock refresh rate
    :param lambda_function: Optional lambda function to schedule if the lock cannot be obtained
    :param schedule_minutes: Ignored unless lambda_function is specified, and is the number of minutes in the
    future to schedule the lambda. If not provided, 1 is assumed.
    """

    assert timeout_seconds > 0
    assert 0 < refresh_seconds < timeout_seconds

    def locker(repo: ResourceLockRepo, name: str) -> AutoRefreshLock:
        return repo.try_acquire_auto_refresh_lock(name, refresh_seconds, timeout_seconds)

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args):
            return __attempt_session_lock(
                lock_type,
                locker,
                lambda_function,
                schedule_minutes,
                wrapped_function,
                *args
            )

        return _inner_wrapper

    return decorator


def session_try_auto_lock(lock_type: str,
                          refresh_seconds: int,
                          lambda_function: Optional[LambdaFunction] = None,
                          schedule_minutes: int = None):
    """
    Use this to decorate functions that want exclusive access to a session by obtaining an auto refresh lock.
    The first argument of the function must be a SessionKey.

    :param lock_type: the lock type name used when forming the lock name. It will be of the form {lock_type}/tenant_id/session_id
    :param refresh_seconds: the lock refresh rate
    :param lambda_function: Optional lambda function to schedule if the lock cannot be obtained
    :param schedule_minutes: Ignored unless lambda_function is specified, and is the number of minutes in the
    future to schedule the lambda. If not provided, 1 is assumed.
    """

    assert refresh_seconds > 0

    def locker(repo: ResourceLockRepo, name: str) -> AutoRefreshLock:
        return repo.try_acquire_auto_refresh_lock(name, refresh_seconds)

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args):
            return __attempt_session_lock(
                lock_type,
                locker,
                lambda_function,
                schedule_minutes,
                wrapped_function,
                *args
            )

        return _inner_wrapper

    return decorator


def session_try_lock(lock_type: str,
                     expire_seconds: int = 15,
                     lambda_function: Optional[LambdaFunction] = None,
                     schedule_minutes: int = None):
    """
    Use this to decorate functions that want exclusive access to a session. The first argument
    of the function must be a SessionKey.

    :param lock_type: the lock type name used when forming the lock name. It will be of the form {lock_type}/tenant_id/session_id
    :param expire_seconds: the number of seconds it is expected the lock will be needed.
    :param lambda_function: Optional lambda function to schedule if the lock cannot be obtained
    :param schedule_minutes: Ignored unless lambda_function is specified, and is the number of minutes in the
    future to schedule the lambda. If not provided, 1 is assumed.
    """

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args):
            return __attempt_session_lock(
                lock_type,
                lambda repo, name: repo.try_acquire(name, expire_seconds),
                lambda_function,
                schedule_minutes,
                wrapped_function,
                *args
            )

        return _inner_wrapper

    return decorator
