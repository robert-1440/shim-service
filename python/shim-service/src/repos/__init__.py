import abc
from typing import Any, List, TypeVar, Generic, Iterable, Callable


class OptimisticLockException(Exception):
    def __init__(self):
        super(OptimisticLockException, self).__init__("Optimistic lock exception.")


Record = TypeVar("Record")


class Serializable(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def serialize(self) -> bytes:
        raise NotImplementedError()


class QueryResult:
    def __init__(self, results: List[Record],
                 next_token: Any = None):
        self.rows = results
        self.next_token = next_token


class QueryResultSet(Generic[Record]):
    def __init__(self,
                 count: int,
                 results: Iterable[Record],
                 token_getter: Callable[[], Any]):
        self.__count = count
        self.__rows = results
        self.__token_getter = token_getter

    @property
    def count(self) -> int:
        return self.__count

    @property
    def next_token(self) -> Any:
        return self.__token_getter()

    def __iter__(self):
        return iter(self.__rows)
