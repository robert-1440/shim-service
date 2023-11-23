import abc
from typing import Optional

from session import Session, UserSession


class UserSessionsRepo(metaclass=abc.ABCMeta):

    def find_by_session(self, session: Session) -> Optional[UserSession]:
        return self.find_user_session(session.tenant_id, session.user_id)

    @abc.abstractmethod
    def find_user_session(self, tenant_id: int, user_id: str) -> Optional[UserSession]:
        raise NotImplementedError()
