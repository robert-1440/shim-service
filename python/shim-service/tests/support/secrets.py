from typing import Any

from bean import BeanName, beans
from botomocks.sm_mock import MockSecretsManagerClient
from cs_client import ConfigServiceSecret
from repos.secrets import ServiceKeys, ServiceKey
from utils.date_utils import get_system_time_in_millis


class TestSecret:
    def __init__(self, name: str, secret_value: str):
        self.name = name
        self.secret_value = secret_value
        self.last_modified = get_system_time_in_millis()

    def to_config_service_secret(self) -> ConfigServiceSecret:
        return ConfigServiceSecret({
            'clientId': "None",
            'clientSecret': self.secret_value,
            'lastModified': self.last_modified
        })


def install(session_mock: Any = None) -> MockSecretsManagerClient:
    client = MockSecretsManagerClient()
    now = get_system_time_in_millis()
    service_keys = ServiceKeys([
        ServiceKey('key1', "key-value1", now),
        ServiceKey('key2', "key-value2", now),
        ServiceKey('key3', "key-value3", now),
    ])
    name = f"shim-service/service-keys"
    payload = service_keys.to_json()
    client.create_secret(Name=name, SecretString=payload, Description="Service keys for Shim Service")
    beans.override_bean(BeanName.SECRETS_MANAGER_CLIENT, client)
    if session_mock is not None:
        session_mock.set_service_keys(service_keys)
    return client
