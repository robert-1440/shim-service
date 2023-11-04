from threading import RLock, Condition


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
