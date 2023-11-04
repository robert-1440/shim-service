import abc
from typing import Optional

from lambda_web_framework.web_exceptions import BadRequestException, GoneException
from session import Session, SessionStatus, verify_session_status, SessionKey
from utils.date_utils import EpochSeconds


class UserSessionExistsException(Exception):
    def __init__(self, session_id: str):
        super(UserSessionExistsException, self).__init__()
        self.session_id = session_id


class CreateSessionRequest:
    def __init__(self, session: Session,
                 worker_timeout_seconds: int):
        self.session = session
        self.initial_session_id = self.session.session_id
        self.worker_timeout_seconds = worker_timeout_seconds


class SessionsRepo(metaclass=abc.ABCMeta):
    @abc.abstractmethod
    def create_session(self, request: CreateSessionRequest):
        raise NotImplementedError()

    def get_session(self,
                    session_key: SessionKey,
                    in_path: bool = False,
                    allow_pending: bool = False,
                    allow_failure: bool = False):
        session = self.find_session(session_key)
        if session is None:
            ex_type = GoneException if in_path else BadRequestException
            raise ex_type("Session is gone.")
        if session.status != SessionStatus.ACTIVE:
            verify_session_status(session, pending_ok=allow_pending, allow_failure=allow_failure)
        return session

    @abc.abstractmethod
    def find_session(self, session_key: SessionKey) -> Optional[Session]:
        raise NotImplementedError()

    @abc.abstractmethod
    def touch(self, session: Session) -> Optional[EpochSeconds]:
        """
        Attempt to update the update time for the given session.

        :param session: the session to update.
        :return: Non None = the expiration time, None if not found.
        """
        raise NotImplementedError()

    @abc.abstractmethod
    def update_session(self, session: Session) -> bool:
        """
        Attempt to update the given session.

        :param session: the session to update.
        :return: True if the session was updated, False if not found or optimistic lock failure.
        """
        raise NotImplementedError()

    def fix_orphaned_session(self, session: Session, session_id: str) -> bool:
        save_session_id = session.session_id
        try:
            session.session_id = session_id
            return self.fix_orphaned_user_session(session)
        finally:
            session.session_id = save_session_id

    def fix_orphaned_user_session(self, session: Session) -> bool:
        raise NotImplementedError()

    def delete_session(self, session: Session):
        raise NotImplementedError()
