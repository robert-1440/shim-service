import sys
import threading
import traceback
from multiprocessing.pool import ThreadPool
from threading import Condition, Thread, RLock
from typing import List, Any, Callable, Optional


class SignalEvent:
    def __init__(self, manual_reset: bool = False):
        """
        Constructs a new event.

        :param manual_reset: True to not clear the signalled state until manually called.
        """
        self.__mutex = RLock()
        self.__condition = Condition()
        self.__manual_reset = manual_reset
        self.__signalled = False

    def notify(self, keep_signalled: bool = False):
        with self.__condition:
            self.__signalled = True
            if keep_signalled:
                self.__manual_reset = True
            if self.__manual_reset:
                self.__condition.notify_all()
            else:
                self.__condition.notify()

    def reset(self):
        with self.__condition:
            self.__signalled = False

    def wait(self, millis: int = None) -> bool:
        amt = millis / 1000 if millis is not None else None
        with self.__condition:
            if self.__signalled or self.__condition.wait(amt):
                if not self.__manual_reset:
                    self.__signalled = False
                return True
            return False

    def assert_wait(self, millis: int):
        result = self.wait(millis)
        assert result


class Task:
    def __init__(self, runner, initial_task_count):
        self.pool = None
        self.runner = runner
        self.initial_task_count = initial_task_count
        self.done_count = 0

    def is_done(self):
        return self.done_count == self.initial_task_count

    def join(self):
        self.pool.join()

    def call(self, object):
        self.runner(object)
        self.done_count += 1


def run_parallel(num_threads: int, object_list: List[Any], runner: Callable[[Any], None]):
    def internal_runner(arg):
        try:
            runner(arg)
        except Exception as ex:
            __show_exception(ex)

    if len(object_list) == 1:
        internal_runner(object_list[0])
    else:
        inner_pool = __submit_parallel(num_threads, object_list, internal_runner)
        inner_pool.join()


def submit_in_parallel(num_threads: int, object_list: List[Any], runner: Callable[[Any], None]) -> Task:
    task = Task(runner, len(object_list))
    num_threads = min(num_threads, len(object_list))

    def run_me(object):
        try:
            task.call(object)
        except Exception as ex:
            __show_exception(ex)

    inner_pool = __submit_parallel(num_threads, object_list, run_me)
    task.pool = inner_pool
    return task


#
# Submits the given object list to a pool of threads to execute the given runner on each object.
#
# Returns the ThreadPool.  The caller should call join() to wait for the tasks to finish.
#
def __submit_parallel(num_threads: int, object_list: List[Any], runner: Callable[[Any], None]) -> ThreadPool:
    if num_threads > len(object_list):
        num_threads = len(object_list)
    inner_pool = ThreadPool(num_threads)
    inner_pool.map_async(runner, object_list)
    inner_pool.close()
    return inner_pool


def start_threads_for(functions_to_call: [Callable], daemon=True):
    thread_list = []
    for f in functions_to_call:
        t = threading.Thread(target=f, daemon=daemon)
        t.start()
        thread_list.append(t)
    return thread_list


def create_thread(function_to_call: Callable, daemon=True,
                  user_object: Any = None,
                  name: str = None) -> threading.Thread:
    def wrapper():
        try:
            if user_object is not None:
                function_to_call(user_object)
            else:
                function_to_call()
        except Exception as ex:
            __show_exception(ex)

    t = threading.Thread(target=wrapper, daemon=daemon, name=name)
    return t


def start_thread(function_to_call: Callable, daemon=True,
                 user_object: Any = None,
                 name: str = None) -> threading.Thread:
    t = create_thread(function_to_call, daemon=daemon, user_object=user_object, name=name)
    t.start()
    return t


def start_threads(function_to_call, thread_count, daemon=True) -> List[threading.Thread]:
    thread_list = []
    for i in range(0, thread_count):
        t = threading.Thread(target=function_to_call, daemon=daemon)
        t.start()
        thread_list.append(t)
    return thread_list


def __show_exception(ex: Exception, prefix_message="Uncaught exception:"):
    stack = f"{type(ex)}: {ex}\n{traceback.print_tb(ex.__traceback__)}\n"
    if prefix_message is None:
        print(stack)
    else:
        print(f"{prefix_message} {ex}\n{traceback.print_tb(ex.__traceback__)}", file=sys.stderr)


def _remove_from_dict(source: dict, key: str) -> Optional[Any]:
    if key in source:
        v = source.get(key)
        del source[key]
        return v
    return None


class _LocalData:
    def __init__(self):
        self.settings = {}
        self.stack = []

    def push(self):
        self.stack.append(self.settings)
        self.settings = dict(self.settings)

    def pop(self):
        if len(self.stack) < 1:
            raise ValueError("Stack is empty")
        del self.settings
        self.settings = self.stack.pop()

    def set(self, name: str, value: Any) -> Any:
        if value is None:
            return _remove_from_dict(self.settings, name)
        current = self.settings.get(name)
        self.settings[name] = value
        return current

    def get(self, name: str) -> Any:
        return self.settings.get(name)

    def remove(self, name: str) -> Any:
        return _remove_from_dict(self.settings, name)


class ThreadLocal:
    def __init__(self):
        self.__thread_local = threading.local()

    def is_present(self):
        return hasattr(self.__thread_local, "data")

    def is_empty(self):
        return not self.is_present()

    def set(self, data: Any):
        self.__thread_local.data = data

    def get(self) -> Optional[Any]:
        if self.is_present():
            return self.__thread_local.data
        return None

    def clear(self):
        if hasattr(self.__thread_local, "data"):
            delattr(self.__thread_local, "data")


class ThreadLocalPropertySet:
    def __init__(self):
        self.__thread_local = threading.local()

    def __get_local(self) -> _LocalData:
        if not hasattr(self.__thread_local, "data"):
            self.__thread_local.data = _LocalData()
        return self.__thread_local.data

    def push(self):
        self.__get_local().push()

    def pop(self):
        self.__get_local().pop()

    def set(self, name: str, value: Any) -> Any:
        return self.__get_local().set(name, value)

    def get(self, name: str) -> Any:
        return self.__get_local().get(name)

    def remove(self, name: str) -> Any:
        return self.__get_local().remove(name)

    def get_bool(self, name: str) -> bool:
        v = self.get(name)
        return v is True

    def __setitem__(self, key, value):
        self.set(key, value)

    def __getitem__(self, item):
        return self.__get_local().settings[item]


def join(thread: Thread, timeout: float = None) -> bool:
    thread.join(timeout)
    return not thread.is_alive()
