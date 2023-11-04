import abc

from repos import Serializable
from session import Session, SessionContext, ContextType


class PollingShutdownException(Exception):
    def __init__(self):
        super(PollingShutdownException, self).__init__("Polling was shutdown.")


class PollingPlatform(metaclass=abc.ABCMeta):

    @classmethod
    def create_session_context(cls, session: Session):
        return SessionContext(
            session.tenant_id,
            session.session_id,
            session.user_id,
            cls.get_context_type(),
            cls.create_initial_polling_settings().serialize()
        )

    @classmethod
    @abc.abstractmethod
    def get_context_type(cls) -> ContextType:
        raise NotImplementedError()

    @classmethod
    @abc.abstractmethod
    def create_initial_polling_settings(cls) -> Serializable:
        raise NotImplementedError
