from typing import Optional

from auth import Credentials
from cs_client.admin import AdminClient
from lambda_web_framework.request import LambdaHttpRequest
from lambda_web_framework.web_exceptions import NotAuthorizedException, BadRequestException
from lambda_web_framework.web_router import Route, Authenticator
from session import manager
from utils import loghelper
from utils.concurrent_cache import ConcurrentTtlCache
from utils.date_utils import get_system_time_in_millis
from utils.string_utils import decode_base64_to_string

logger = loghelper.get_logger(__name__)

_GRACE_TIME_MILLIS = 5555


class _AuthParts:
    def __init__(self, name: str, request_time: int, signature: str):
        # Signature is formatted as follows
        # name:request_time:signature
        self.name = name
        self.request_time = request_time
        self.signature = signature

    def validate(self, request: LambdaHttpRequest, creds: Credentials):
        result = creds.sign(request.method, request.path, self.request_time, request.body)
        if result.signature == self.signature:
            request.set_credentials(creds)
            return
        logger.warning(f"Signature mismatch. Expected signing string is '{result.signing_string}'.")
        raise NotAuthorizedException("Signature mismatch.")


def __decode_base64(content: str) -> Optional[str]:
    v = decode_base64_to_string(content, fail_on_error=False)
    if v is None:
        logger.error(f"Invalid base64 content: '{content}'")
    return v


def __parse_int(v: str) -> Optional[int]:
    try:
        return int(v)
    except Exception:
        return None


def _parse_auth_parts(token: str) -> Optional[_AuthParts]:
    decoded = __decode_base64(token)
    if decoded is not None:
        values = decoded.split(':', 3)
        if len(values) == 3:
            request_time = __parse_int(values[1])
            if request_time is not None:
                diff = abs(get_system_time_in_millis() - request_time)
                if diff <= _GRACE_TIME_MILLIS:
                    return _AuthParts(values[0], request_time, values[2])
    return None


_CACHE_MINUTES = 20


class AuthenticatorImpl(Authenticator):
    def __init__(self, admin_client: AdminClient):
        self.admin_client = admin_client
        self.creds_cache = ConcurrentTtlCache(1000, _CACHE_MINUTES * 60,
                                              loader=self.__find_creds)

    def __find_creds(self, name: str) -> Optional[Credentials]:
        cc = self.admin_client.find_credentials(name)
        return Credentials(cc) if cc is not None else None

    def __get_creds(self, name: str) -> Credentials:
        creds = self.creds_cache.get(name)
        if creds is None:
            raise NotAuthorizedException(f"Unable to find '{name}' credentials.")
        return creds

    def authenticate(self, route: Route, request: LambdaHttpRequest):
        values = request.get_required_header('Authorization').split(' ', maxsplit=1)
        if len(values) == 2 and values[0] == '1440-HMAC-SHA256-A':
            auth_parts = _parse_auth_parts(values[1])
            if auth_parts is not None:
                creds = self.__get_creds(auth_parts.name)
                auth_parts.validate(request, creds)
                if route.session_required or route.api_required:
                    manager.verify_session(request, creds)
                return

        raise BadRequestException("Invalid Authorization header.")

    def clear_cache(self):
        self.creds_cache.clear()
