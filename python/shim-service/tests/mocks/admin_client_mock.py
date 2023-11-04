from cs_client import ConfigServiceSecret
from utils.date_utils import get_system_time_in_millis


class MockAdminClient():
    def __init__(self):
        pass

    def find_secret(self, name: str):
        node = {
            'clientId': 'clientId',
            'clientSecret': 'clientSecret',
            'lastModified': get_system_time_in_millis(),
        }
        return ConfigServiceSecret(node)
