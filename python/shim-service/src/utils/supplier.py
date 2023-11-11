import abc
from threading import RLock
from typing import Callable, Generic, TypeVar, Optional

T = TypeVar("T")


class Supplier(Generic[T], metaclass=abc.ABCMeta):
    def get(self, callback_initializer: Callable = None) -> T:
        """
        The value of the supplier.
        """
        raise NotImplementedError()


class MemoizedSupplier(Supplier):
    """
    A supplier that will initialize its value, based on the given Callable, the first time get() is called.

    This is thread-safe.
    """

    def __init__(self, getter: Callable):
        """
        Constructs a new supplier.

        :param getter: the getter to call to initialize the value when get() is called for the first time.
        """
        assert getter is not None
        self.__value_set = False
        self.__mutex = RLock()
        self.__value: Optional[T] = None
        self.__getter = getter

    def get(self, callback_initializer: Callable = None) -> T:
        if not self.__value_set:
            m = self.__mutex
            if m is not None:
                with m:
                    if not self.__value_set:
                        self.__value = self.__getter()
                        self.__value_set = True
                        del self.__mutex
                        del self.__getter
                        if callback_initializer is not None:
                            callback_initializer()

        return self.__value
