import abc
import json
from typing import Optional, Tuple, List, Union, Dict, Any

from lambda_web_framework.web_exceptions import NotAuthorizedException, EntityExistsException
from utils import hash_utils
from utils.date_utils import EpochMilliseconds


class ServiceKey:
    def __init__(self, key_id: str, key: str, time_created: EpochMilliseconds):
        self.key_id = key_id
        self.key = key
        self.timeCreated = time_created

    def to_record(self):
        record = dict(self.__dict__)
        record.pop('key_id')
        return record

    def sign(self,
             method: str,
             path: str,
             request_time: int,
             body: Optional[str] = None) -> Tuple[str, str]:
        sig = f"{self.key_id}:{path}:{method}:{request_time}"
        if body is not None:
            sig += f":{hash_utils.hash_sha256_to_hex(body)}"
        signed = hash_utils.hmac_sha256_to_hex(sig, self.key)
        return sig, signed


class ServiceKeys:
    def __init__(self, keys: List[ServiceKey]):
        self.keys = keys

    @staticmethod
    def from_json(input_string: Union[str, dict]):
        record = json.loads(input_string) if type(input_string) is str else input_string
        keys = []
        for key_id, value in record['keys'].items():
            keys.append(ServiceKey(key_id, value['key'], value['timeCreated']))
        return ServiceKeys(keys)

    def to_json(self) -> str:
        return json.dumps(self.to_record())

    def to_record(self) -> Dict[str, Any]:
        keys = {}
        record = {"keys": keys}
        for key in self.keys:
            keys[key.key_id] = key.to_record()
        return record


class PushNotificationProviderCredentials:
    def __init__(self, content: Dict[str, Any]):
        self.content = content

    @classmethod
    def from_json(cls, data: Optional[Union[str, dict]]):
        if data is None:
            return None
        record = data if isinstance(data, dict) else json.loads(data)
        return cls(record)


class SecretsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def find_service_keys(self) -> Optional[ServiceKeys]:
        raise NotImplementedError()

    def get_service_keys(self) -> ServiceKeys:
        keys = self.find_service_keys()
        if keys is None:
            raise NotAuthorizedException("No service keys.")
        return keys

    def create_service_keys(self, service_keys: ServiceKeys):
        if not self._create_service_keys(service_keys):
            raise EntityExistsException("Service keys already deployed.")

    @abc.abstractmethod
    def _create_service_keys(self, service_keys: ServiceKeys) -> bool:
        raise NotImplementedError()
