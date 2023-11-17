import abc

from bean import BeanName, inject
from instance import Instance
from session import Session
from utils.uri_utils import Uri


class SfdcAuthenticator(metaclass=abc.ABCMeta):

    def __init__(self, session: Session):
        self.__tenant_id = session.tenant_id
        self.__session_id = session.session_id
        self.__user_id = session.user_id
        self.__expiration_seconds = session.expiration_seconds
        self.__instance_uri = Uri.parse(session.instance_url)

    @property
    def instance_uri(self) -> Uri:
        return self.__instance_uri

    @property
    def tenant_id(self) -> int:
        return self.__tenant_id

    @property
    def session_id(self) -> str:
        return self.__session_id

    def expiration_seconds(self) -> int:
        return self.__expiration_seconds

    @abc.abstractmethod
    def get_access_token(self) -> str:
        raise NotImplementedError()



class _SfdcAuthenticatorImpl(SfdcAuthenticator):
    def __init__(self, session: Session, instance: Instance):
        super(_SfdcAuthenticatorImpl, self).__init__(session)
        self.instance = instance
        self.access_token = session.access_token

    def get_access_token(self) -> str:
        return self.access_token


@inject(bean_instances=BeanName.INSTANCE)
def create_authenticator(session: Session, instance: Instance) -> SfdcAuthenticator:
    return _SfdcAuthenticatorImpl(session, instance)
