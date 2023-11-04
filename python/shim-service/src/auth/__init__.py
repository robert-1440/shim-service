import base64
from typing import Optional, Union

from cs_client import ConfigServiceCredentials, SignResult
from utils import string_utils
from utils.obfuscation import DataObfuscator


class Credentials:

    def __init__(self, source: ConfigServiceCredentials):
        self.source = source
        self.__obfuscator: Optional[DataObfuscator] = None

    def has_access_to_tenant(self, tenant_id: int) -> bool:
        return self.source.has_access_to_tenant(tenant_id)

    def assert_tenant_access(self, tenant_id: int):
        self.source.assert_tenant_access(tenant_id)

    def sign(self,
             method: str,
             path: str,
             request_time: int,
             body: Optional[str] = None) -> SignResult:
        return self.source.sign(method, path, request_time, body)

    def __get_obfuscator(self):
        if self.__obfuscator is None:
            self.__obfuscator = DataObfuscator(
                self.source.password_bytes,
                self.source.name,
                self.source.client_id
            )

        return self.__obfuscator

    def obfuscate_data(self, data: Union[str, bytes]) -> str:
        return string_utils.encode_to_urlsafe_base64string(self.__get_obfuscator().obfuscate(data)).rstrip('=')

    def clarify_data(self, base64_encoded_data: str) -> str:
        if not base64_encoded_data.endswith('=='):
            base64_encoded_data += '=='
        decoded = base64.urlsafe_b64decode(base64_encoded_data)
        result = self.__get_obfuscator().clarify(decoded)
        return result.decode('utf-8')
