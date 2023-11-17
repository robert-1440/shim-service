import threading
import time
from threading import RLock
from typing import List, Any

from better_test_case import BetterTestCase
from support.thread_utils import SignalEvent
from utils.threading_utils import AsyncProcessorGroup, submit_blocks_in_parallel


class Tester:
    def __init__(self, max_threads: int,
                 partition_size: int = 25,
                 max_queue_size: int = 512):
        self.__max_threads = max_threads
        self.__max_queue_size = max_queue_size
        self.threads_seen = set()
        self.errors_seen = []
        self.on_submits_seen = []
        self.processed_count = 0
        self.__mutex = RLock()
        self.group = AsyncProcessorGroup(max_threads=max_threads,
                                         partition_size=partition_size,
                                         processor=self.__processor,
                                         max_queue_size=max_queue_size,
                                         on_submit=self.__on_submit,
                                         on_error=self.__on_error)

    def add(self, *args):
        for arg in args:
            if isinstance(arg, list):
                for obj in arg:
                    self.group.add(obj)
            else:
                self.group.add(arg)

    def join(self, timeout: float = None):
        return self.group.join(timeout)

    def __on_submit(self, obj_list: List[Any]):
        with self.__mutex:
            self.on_submits_seen.append(obj_list)

    def __on_error(self, ex: BaseException):
        with self.__mutex:
            self.errors_seen.append(ex)

    def __processor(self, obj_list: List[Any]):
        with self.__mutex:
            self.processed_count += len(obj_list)
            self.threads_seen.add(threading.current_thread())

        for obj in obj_list:
            if isinstance(obj, bool) and not obj:
                raise ValueError("Failed")
            elif isinstance(obj, float):
                time.sleep(obj)
            elif isinstance(obj, SignalEvent):
                obj.wait(30)


class TestSuite(BetterTestCase):

    def test_async_processor_group_empty(self):
        t = Tester(5, 10)
        t.join()
        self.assertEqual(0, t.processed_count)

    def test_async_processor_group_1(self):
        t = Tester(5, 10)
        t.add("ONE")
        t.join()
        self.assertEqual(1, t.processed_count)
        self.assertEqual(1, len(t.threads_seen))
        self.assertEqual(1, len(t.on_submits_seen))

    def test_async_processor_group_multi(self):
        t = Tester(5, 5)
        event = SignalEvent(manual_reset=True)
        for i in range(100):
            t.add([event, 0.01, False, 0, 0])

        while len(t.threads_seen) < 5:
            time.sleep(.1)
        event.notify()
        t.join()
        self.assertEqual(500, t.processed_count)
        self.assertHasLength(100, t.on_submits_seen)
        self.assertHasLength(100, t.errors_seen)

        # Note: our thread finishes it up
        self.assertEqual(6, len(t.threads_seen))
        self.assertIn(threading.current_thread(), t.threads_seen)

    def test_submit_in_parallel(self):
        threads_seen = set()
        mutex = RLock()
        total = 0
        continue_event = SignalEvent(manual_reset=True)
        multi = False

        def receiver(obj_list: List[Any]):
            threads_seen.add(threading.current_thread())
            if multi:
                if len(threads_seen) > 1:
                    continue_event.notify()

            with mutex:
                nonlocal total
                total += len(obj_list)

            if multi:
                continue_event.wait(5000)

        block = [i for i in range(0, 10)]
        submit_blocks_in_parallel(
            block,
            10,
            5,
            receiver
        )

        self.assertHasLength(1, threads_seen)
        self.assertEqual(10, total)

        continue_event.reset()
        threads_seen.clear()
        total = 0
        multi = True
        submit_blocks_in_parallel(
            block * 2,
            10,
            5,
            receiver
        )

        self.assertHasLength(2, threads_seen)
        self.assertEqual(20, total)





