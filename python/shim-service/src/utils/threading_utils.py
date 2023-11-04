import threading
from threading import Thread
from typing import Callable, Any, List


def create_thread(function_to_call: Callable,
                  daemon=True,
                  user_object: Any = None,
                  name: str = None) -> threading.Thread:
    def wrapper():
        if user_object is not None:
            function_to_call(user_object)
        else:
            function_to_call()

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
