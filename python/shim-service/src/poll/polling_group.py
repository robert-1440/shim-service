import abc
import time
from threading import Thread, RLock
from typing import List, Callable, Optional, TypeVar, Any

from repos import QueryResult
from repos.resource_lock import ResourceLockRepo, ResourceLock
from utils import loghelper, exception_utils, threading_utils
from utils.signal_event import SignalEvent
from utils.throttler import Throttler
from utils.timer_utils import Timer

Invoker = Callable[[], None]
E = TypeVar("E")

logger = loghelper.get_logger(__name__)


class LockAndEvent:
    def __init__(self, event: E, lock: ResourceLock):
        self.event = event
        self.lock = lock
        self.failed = False
        self.after_release: Optional[Callable] = None
        self.update_action_time = True
        self.user_object = None

    @property
    def tenant_id(self) -> int:
        return self.event.tenant_id

    @property
    def session_id(self) -> str:
        return self.event.session_id

    def release(self):
        self.lock.release()
        if self.after_release is not None:
            self.after_release()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()


class AbstractProcessorGroup(metaclass=abc.ABCMeta):
    def __init__(self, resource_lock_repo: ResourceLockRepo,
                 refresh_seconds: int,
                 max_working_count: int,
                 max_collect_seconds: int
                 ):
        self.resource_lock_repo = resource_lock_repo
        self.max_working_count = max_working_count
        self.refresh_seconds = refresh_seconds
        self.max_collect_seconds = max_collect_seconds

        self.threads: List[Thread] = []
        self.submit_count = 0
        self.working_count = 0
        self.mutex = RLock()
        self.signal_event = SignalEvent()
        self.invoke_throttler = Throttler(10000, self.invoke_lambda)

    @abc.abstractmethod
    def invoke_lambda(self):
        raise NotImplementedError()

    @abc.abstractmethod
    def form_lock_name(self, event: E):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_action_time(self, event: E, seconds_in_future: int) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def poll(self, le: LockAndEvent):
        raise NotImplementedError()

    def dec_submit_count(self):
        with self.mutex:
            self.submit_count -= 1
            self.signal_event.notify()

    def invoke_again(self):
        self.invoke_throttler.add_invocation()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.invoke_throttler.close()

    def should_poll(self, le: LockAndEvent) -> bool:
        raise NotImplementedError()

    def __inner_worker(self, event: E):
        # First, try to lock the resource for the event
        le = None
        try:
            le = self.__try_lock(event)
        finally:
            if le is None:
                self.dec_submit_count()
        if le is None:
            return
        logger.info("Worker starting.")
        with le:
            le.after_release = self.invoke_again

            if not self.should_poll(le):
                self.dec_submit_count()
                return

            with self.mutex:
                self.working_count += 1
                self.submit_count -= 1
                self.signal_event.notify()

            try:
                self.poll(le)
                if le.update_action_time:
                    self.update_action_time(le.event, 0)

            except BaseException as ex:
                logger.severe(f"Failed during poll: {exception_utils.dump_ex(ex)}")

        logger.info("Worker ending.")

    def worker(self, event: E):
        try:
            self.__inner_worker(event)
        except BaseException as ex:
            logger.severe("Exception invoking worker", ex=ex)

    def add(self, event: E) -> bool:
        """
        Try to add the event for processing.

        :param event: the event.
        :return: False if we are processing the max events.
        """
        if not self.is_full(True):
            t = threading_utils.start_thread(self.worker, user_object=event)
            self.threads.append(t)
            return True
        return False

    def is_empty(self) -> bool:
        return len(self.threads) == 0

    def join(self, timeout: float) -> bool:
        if len(self.threads) == 0:
            return True

        for t in self.threads:
            if not t.is_alive():
                self.threads.remove(t)
                return self.join(timeout)
            else:
                t.join(timeout)
                if not t.is_alive():
                    self.threads.remove(t)
            break

        return len(self.threads) == 0

    def is_full(self, increment: bool = False):
        timer = Timer(self.max_collect_seconds)
        while timer.has_time_left():
            with self.mutex:
                if self.working_count == self.max_working_count:
                    return True
                total = self.working_count + self.submit_count
                if total < self.max_working_count:
                    if increment:
                        self.submit_count += 1
                    return False
            if not increment:
                return False
            self.signal_event.wait(timer.get_delay_time_millis(50))
        return True

    def __try_lock(self, event: E) -> Optional[LockAndEvent]:
        # We need to lock on tenant id and user id, since we do not want the same user to be polling more than once
        name = self.form_lock_name(event)
        logger.info(f"Attempting to lock resource {name} ...")
        lock = self.resource_lock_repo.try_acquire(name, self.refresh_seconds)
        if lock is None:
            logger.info(f"{name} is currently locked.")
        elif lock.execute_and_release_on_false(lambda:
                                               self.update_action_time(event, self.refresh_seconds)):
            return LockAndEvent(event, lock)
        return None

    def thread_count(self) -> int:
        return len(self.threads)

    @abc.abstractmethod
    def query_events(self, limit: int, next_token: Any) -> QueryResult:
        raise NotImplementedError()

    def collect(self):
        # Sleep for a bit, so we can get as many as possible
        time.sleep(.5)
        next_token = None
        full = False
        while not full:
            result = self.query_events(
                limit=self.max_working_count,
                next_token=next_token
            )
            next_token = result.next_token
            if len(result.rows) == 0:
                if next_token is None:
                    break
            else:
                for event in result.rows:
                    if not self.add(event):
                        full = True
                        break
            if full or next_token is None or self.is_full():
                break

        if full or next_token is not None:
            # This means we have more than the max out there, let another process grab them
            self.invoke_again()
