from typing import Any, Optional

from aws import is_not_found_exception, is_invalid_request
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

    def __get_secret_value(self, name: str) -> Optional[str]:
        try:
            response = self.client.get_secret_value(SecretId=name)
        except Exception as ex:
            if is_not_found_exception(ex) or is_invalid_request(ex):
                return None
            raise ex
        return response['SecretString']
