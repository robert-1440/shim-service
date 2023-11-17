import threading
from queue import Queue
from threading import Thread
from typing import Callable, Any, List, TypeVar, Generic, Optional, Iterable

from utils import loghelper
from utils.collection_utils import BufferedList
from utils.exception_utils import dump_ex
from utils.signal_event import SignalEvent

logger = loghelper.get_logger(__name__)


def create_thread(function_to_call: Callable,
                  daemon=True,
                  user_object: Any = None,
                  name: str = None) -> threading.Thread:
    def wrapper():
        try:
            if user_object is not None:
                function_to_call(user_object)
            else:
                function_to_call()
        except BaseException as ex:
            logger.error(f"Unhandled exception: {dump_ex(ex)})")

    t = threading.Thread(target=wrapper, daemon=daemon, name=name)
    return t


def start_thread(function_to_call: Callable, daemon=True,
                 user_object: Any = None,
                 name: str = None) -> threading.Thread:
    t = create_thread(function_to_call, daemon=daemon, user_object=user_object, name=name)
    t.start()
    return t


class ThreadGroup:
    def __init__(self, threads: List[Thread]):
        self.__threads = threads

    def thread_count(self) -> int:
        return len(self.__threads)

    def join(self, timeout: float) -> bool:
        if len(self.__threads) == 0:
            return True

        for t in self.__threads:
            if not t.is_alive():
                self.__threads.remove(t)
                return self.join(timeout)
            else:
                t.join(timeout)
                if not t.is_alive():
                    self.__threads.remove(t)
            break

        return len(self.__threads) == 0


T = TypeVar("T")


class AsyncProcessorGroup(BufferedList[T], Generic[T]):
    def __init__(self,
                 max_threads: int,
                 partition_size: int,
                 processor: Callable[[List[T]], None],
                 max_queue_size: int = 512,
                 on_submit: Callable[[List[T]], None] = None,
                 on_error: Callable[[BaseException], None] = None):
        assert max_threads > 0
        assert partition_size > 0
        assert max_queue_size > 0
        super(AsyncProcessorGroup, self).__init__(max_size=partition_size, flusher=self.__submit)
        self.__max_threads = max_threads
        self.__partition_size = partition_size
        self.__processor = processor
        self.__max_queue_size = max_queue_size
        self.__on_submit = on_submit
        self.__on_error = on_error
        self.__threads: Optional[List[Thread]] = None
        self.__queue: Optional[Queue] = None

    def __setup(self):
        self.__queue = Queue(maxsize=self.__max_queue_size)
        self.__signal_event = SignalEvent()
        self.__threads = []

    def __submit(self, obj_list: List[T]):
        if self.__queue is None:
            self.__setup()
        count = len(self.__threads)
        if count == 0 or (self.__queue.qsize() > 0 and count < self.__max_threads):
            t = start_thread(self.__worker)
            self.__threads.append(t)

        self.__queue.put(obj_list)

    def __worker(self):
        while True:
            obj_list = self.__queue.get()
            self.__queue.task_done()
            if obj_list is None:
                break
            self.__execute(obj_list)

    def __execute(self, obj_list: List[T]):
        if self.__on_submit is not None:
            self.__on_submit(obj_list)
        try:
            self.__processor(obj_list)
        except BaseException as ex:
            if self.__on_error is not None:
                self.__on_error(ex)
            else:
                logger.error(f"Unhandled exception: {dump_ex(ex)}")

    def join(self, timeout: float = None):
        if len(self) > 0:
            self.__execute(list(self))

        if self.__queue is not None:
            for t in self.__threads:
                self.__queue.put(None)
            for t in self.__threads:
                t.join(timeout)


def submit_blocks_in_parallel(
        object_list: Iterable[T],
        partition_size: int,
        max_threads: int,
        processor: Callable[[List[T]], None],
        max_queue_size: int = 512,
        on_submit: Callable[[List[T]], None] = None):
    if isinstance(object_list, list) and len(object_list) <= partition_size:
        processor(object_list)
        return

    group = AsyncProcessorGroup(
        max_threads,
        partition_size,
        processor,
        max_queue_size=max_queue_size,
        on_submit=on_submit
    )
    group.add_all(object_list)
    group.join(30)
