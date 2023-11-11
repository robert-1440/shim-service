from traceback import print_exc

from auth import Credentials
from lambda_web_framework.web_exceptions import NotAuthorizedException
from session import SessionKey, logger


class SessionToken(SessionKey):
    def __init__(self, tenant_id: int, session_id: str, user_id: str):
        self.session_id = session_id
        self.tenant_id = tenant_id
        self.user_id = user_id

    def serialize(self, creds: Credentials) -> str:
        token = f"e40~{self.tenant_id}~{self.session_id}~{self.user_id}"
        return creds.obfuscate_data(token)

    def __eq__(self, other):
        return isinstance(other, SessionToken) and \
            self.session_id == other.session_id and \
            self.tenant_id == other.tenant_id and \
            self.user_id == other.user_id

    @classmethod
    def deserialize(cls, creds: Credentials, token: str):
        try:
            data = creds.clarify_data(token)
            values = data.split('~')
            if len(values) == 4 and values[0] == 'e40':
                return SessionToken(int(values[1]), values[2], values[3])
            raise ValueError(f"Token '{token}' is invalid.")
        except Exception as ex:
            print_exc()
            logger.warning(f"Attempt to decrypt token failed: {ex}")

        raise NotAuthorizedException("Invalid session token.")
