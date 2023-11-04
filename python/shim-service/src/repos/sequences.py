import abc
from typing import Callable, Any

SequenceCaller = Callable[[int], None]


class SequenceRepo(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def execute(self, tenant_id: int, name: str, max_lock_seconds: int, sequence_caller: SequenceCaller) -> Any:
        raise NotImplementedError()
