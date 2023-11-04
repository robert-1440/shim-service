import re
from typing import Any, Optional

from aws import is_not_found_exception, is_invalid_request, is_resource_exists
from repos.secrets import SecretsRepo, ServiceKeys

_NAME_PATH = f"shim-service/"

_SERVICE_KEYS = "service-keys"
_PUSH_PROVIDER_CREDS = "push-provider-creds"

_NAME_REGEX = r"^[a-zA-Z0-9-_/]+$"


class AwsSecretsRepo(SecretsRepo):
    def __init__(self, sm_client: Any):
        self.client = sm_client

    def find_service_keys(self) -> Optional[ServiceKeys]:
        v = self.__get_secret_value(f"{_NAME_PATH}{_SERVICE_KEYS}")
        return ServiceKeys.from_json(v) if v else None

    def _create_service_keys(self, service_keys: ServiceKeys) -> bool:
        return self.__create_entry(_SERVICE_KEYS, "Service keys for Shim Service",
                                   service_keys.to_json())

    def __get_secret_value(self, name: str) -> Optional[str]:
        try:
            response = self.client.get_secret_value(SecretId=name)
        except Exception as ex:
            if is_not_found_exception(ex) or is_invalid_request(ex):
                return None
            raise ex
        return response['SecretString']

    def __create_entry(self,
                       name: str,
                       description: str,
                       secret: str) -> bool:
        assert secret is not None
        assert re.fullmatch(_NAME_REGEX, name)
        name = f"{_NAME_PATH}{name}"
        args = {"Name": name, "SecretString": secret, 'Description': description}
        try:
            self.client.create_secret(**args)
            return True
        except Exception as ex:
            if is_resource_exists(ex):
                return False
            raise ex
