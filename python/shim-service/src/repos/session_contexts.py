import abc
from typing import Optional, List

from aws.dynamodb import DynamoDbItem
from pending_event import PendingEvent
from repos import Serializable
from session import Session, ContextType, SessionContext, SessionKey


class SessionContextAndFcmToken(SessionKey):
    context: SessionContext

    def __init__(self,
                 context: SessionContext,
                 token: Optional[str]):
        self.context = context
        self.token = token

    @property
    def tenant_id(self) -> int:
        return self.context.tenant_id

    @property
    def session_id(self) -> str:
        return self.context.session_id


class SessionContextsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def create_session_contexts(self,
                                session: Session,
                                session_data: bytes,
                                contexts: List[SessionContext]) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def find_session_context(self,
                             session_key: SessionKey,
                             context_type: ContextType) -> Optional[SessionContext]:
        raise NotImplementedError()

    @abc.abstractmethod
    def find_session_context_with_fcm_token(self,
                                            session_key: SessionKey,
                                            context_type: ContextType) -> Optional[SessionContextAndFcmToken]:
        raise NotImplementedError()

    @abc.abstractmethod
    def update_session_context(self, context: SessionContext, new_data: Serializable = None) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_session_context(self,
                               session_key: SessionKey,
                               context_type: ContextType) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_failed(self, context: SessionContext, message: str, pending_event: PendingEvent = None) -> bool:
        """
        Sets the session to failed and deletes all contexts.

        :param context: the session context.
        :param message: the failure message.
        :param pending_event: optional associated pending event to delete.
        :return: True if all records were found
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_by_row_keys(self, row_keys: List[DynamoDbItem]):
        """
        Delete contexts for the given row keys.  It is expected that the keys came directly from a DynamoDb stream
        notification, and is already in DynamoDb format for the ServiceSession keys.

        :param row_keys: the list of keys.
        """
        raise NotImplementedError()

