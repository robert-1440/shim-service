import abc
import urllib.parse
from time import time_ns
from typing import Optional, Tuple, List

from lambda_web_framework.web_exceptions import ForbiddenException
from repos.secrets import ServiceKey
from utils import hash_utils, loghelper
from utils.http_client import RequestBuilder
from utils.string_utils import encode_to_base64string

DEFAULT_URL = "https://configuration.1440.io/"

logger = loghelper.get_logger(__name__)


class AbstractCredentials(metaclass=abc.ABCMeta):

    def auth(self, b: RequestBuilder):
        u = urllib.parse.urlparse(b.get_uri())
        req_time = time_ns() // 1_000_000
        _, sig = self.sign(u.path, b.get_method().name, req_time, b.get_body())
        b.header("X-1440-Signature", sig)
        b.authorization("1440-HMAC-SHA256", str(req_time))
        self._finish_auth(b)
        return b

    @abc.abstractmethod
    def get_id(self) -> str:
        raise NotImplementedError()

    @abc.abstractmethod
    def _finish_auth(self, b: RequestBuilder):
        raise NotImplementedError()

    @abc.abstractmethod
    def sign(self,
             path: str,
             method: str,
             request_time: int,
             body: Optional[str] = None):
        raise NotImplementedError()


class ServiceKeyCredentials(AbstractCredentials):
    def __init__(self, service_name: str, key: ServiceKey):
        self.service_name = service_name
        self.key = key

    def sign(self,
             path: str,
             method: str,
             request_time: int,
             body: Optional[str] = None) -> Tuple[str, str]:
        return self.key.sign(method, path, request_time, body)

    def get_id(self) -> str:
        return self.service_name

    def _finish_auth(self, b: RequestBuilder):
        b.header("X-1440-Service-Key", encode_to_base64string(f"{self.service_name}\t{self.key.key_id}"))


class AuthDetails:
    def __init__(self, target_id: str, signing_string: str, signature: str):
        self.target_id = target_id
        self.signing_string = signing_string
        self.signature = signature

    def tokenize(self):
        return encode_to_base64string(f"{self.signing_string} {self.signature}")


class SignResult:
    def __init__(self, signing_string: str, signature: str):
        self.signing_string = signing_string
        self.signature = signature


class ConfigServiceSecret:
    def __init__(self, node: dict):
        self.client_id = node['clientId']
        self.client_secret = node['clientSecret']
        self.last_modified = node['lastModified']
        self.attributes = node.get('attributes')

    def to_record(self):
        record = {
            'clientId': self.client_id,
            'clientSecret': self.client_secret,
            'lastModified': self.last_modified
        }
        if self.attributes is not None:
            record['attributes'] = self.attributes
        return record


class ConfigServiceCredentials:
    def __init__(self, name: str, node: dict):
        self.name = name
        self.client_id: str = node['clientId']
        self.password_bytes: bytes = node['password'].encode('utf-8')
        self.scopes: Optional[List[str]] = node.get('scopes')
        self.tenant_ids: Optional[List[str]] = node.get('tenantIds')

    def sign(self,
             method: str,
             path: str,
             request_time: int,
             body: Optional[str] = None) -> SignResult:
        sig = f"{self.name}:{self.client_id}:{path}:{method}:{request_time}"
        if body is not None:
            b = hash_utils.hash_sha512_to_hex(body)
            sig += f":{b}"
        return SignResult(sig, hash_utils.hmac_sha256_to_hex(sig, self.password_bytes))

    def sign_string(self, string_value: str) -> str:
        return hash_utils.hmac_sha256_to_hex(string_value, self.password_bytes)

    def has_access_to_tenant(self, tenant_id: int) -> bool:
        return self.tenant_ids is not None and tenant_id in self.tenant_ids

    def assert_tenant_access(self, tenant_id: int):
        if not self.has_access_to_tenant(tenant_id):
            logger.warning(f"Attempt to access tenant {tenant_id} with creds: {self.name}")
            raise ForbiddenException(f"Access to organization not allowed.")
