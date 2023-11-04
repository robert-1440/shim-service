from bean import BeanName, beans
from cs_client import ConfigServiceSecret
from repos.secrets import ServiceKeys, ServiceKey, SecretsRepo
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


def setup_mock():
    now = get_system_time_in_millis()
    service_keys = ServiceKeys([
        ServiceKey('key1', "key-value1", now),
        ServiceKey('key2', "key-value2", now),
        ServiceKey('key3', "key-value3", now),
    ])

    repo: SecretsRepo = beans.get_bean_instance(BeanName.SECRETS_REPO)

    repo.create_service_keys(service_keys)
