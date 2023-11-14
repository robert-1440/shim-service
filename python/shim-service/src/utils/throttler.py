from threading import RLock, Thread
from traceback import print_exception
from typing import Callable, Optional

from utils import threading_utils
from utils.date_utils import get_system_time_in_millis
from utils.signal_event import SignalEvent


class Throttler:
    def __init__(self, throttle_millis: int, caller: Callable):
        assert throttle_millis > 0
        self.__throttle_millis = throttle_millis
        self.__caller = caller
        self.__event = SignalEvent()
        self.__mutex = RLock()
        self.__any_waiting = False
        self.__shutdown = False
        self.__thread: Optional[Thread] = None

    def __worker(self):
        start_time = None
        sleep_time = 10000
        while True:
            self.__event.wait(sleep_time)
            invoke = False
            with self.__mutex:
                if self.__any_waiting:
                    if self.__shutdown:
                        invoke = True
                    else:
                        if start_time is None:
                            start_time = get_system_time_in_millis()
                            sleep_time = self.__throttle_millis
                        else:
                            elapsed = get_system_time_in_millis() - start_time
                            if elapsed >= self.__throttle_millis:
                                invoke = True
                            else:
                                sleep_time = self.__throttle_millis - elapsed

                    if invoke:
                        self.__any_waiting = False
                        start_time = None
                        sleep_time = 10000
            if invoke:
                try:
                    self.__caller()
                except BaseException as ex:
                    print_exception(ex)

            if self.__shutdown:
                break

    def add_invocation(self):
        with self.__mutex:
            assert not self.__shutdown, "closed"
            self.__any_waiting = True
            if self.__thread is None:
                self.__thread = threading_utils.start_thread(self.__worker)
            self.__event.notify()

    def close(self):
        with self.__mutex:
            if not self.__shutdown:
                self.__shutdown = True
                if self.__thread is not None:
                    self.__event.notify(keep_signalled=True)
        if self.__thread is not None:
            self.__thread.join(10)
