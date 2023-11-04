import abc
from typing import Optional

from session import ContextType, SessionContext, SessionKey


class SfdcSessionDataAndContext:
    def __init__(self, data: bytes, context: SessionContext):
        self.data = data
        self.context = context


class SfdcSessionsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def load_data(self, session_key: SessionKey) -> Optional[bytes]:
        raise NotImplementedError()

    @abc.abstractmethod
    def load_data_and_context(self,
                              session_key: SessionKey,
                              context_type: ContextType) -> Optional[SfdcSessionDataAndContext]:
        raise NotImplementedError()
