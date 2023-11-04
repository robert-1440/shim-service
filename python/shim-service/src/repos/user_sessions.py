import abc
from typing import Optional

from session import Session, UserSession


class UserSessionsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def find_user_session(self, session: Session) -> Optional[UserSession]:
        raise NotImplementedError()
