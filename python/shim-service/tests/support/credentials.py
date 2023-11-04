import json
from typing import List, Optional, Tuple, Any, Dict

from auth import Credentials
from cs_client import ConfigServiceCredentials
from utils import hash_utils


class TestCredentials:
    def __init__(self, name: str,
                 client_id: str,
                 password: str,
                 scopes: Optional[List[str]] = None,
                 tenant_ids: Optional[List[int]] = None):
        self.name = name
        self.client_id = client_id
        self.password = password
        self.scopes = scopes
        self.tenant_ids = tenant_ids
        self.__creds: Optional[Credentials] = None

    def to_credentials(self):
        if self.__creds is None:
            self.__creds = Credentials(ConfigServiceCredentials(self.name,
                                                                {
                                                                    'clientId': self.client_id,
                                                                    'password': self.password,
                                                                    'tenantIds': self.tenant_ids
                                                                }))
        return self.__creds

    def sign(self,
             method: str,
             path: str,
             request_time: int,
             body: Optional[str] = None) -> Tuple[str, str]:
        sig = f"{self.name}:{self.client_id}:{path}:{method}:{request_time}"
        if body is not None:
            b = hash_utils.hash_sha512_to_hex(body)
            sig += f":{b}"
        return sig, hash_utils.hmac_sha256_to_hex(sig, self.password)

    def to_record(self) -> Dict[str, Any]:
        record = {
            'clientId': self.client_id,
            'password': self.password
        }
        if self.scopes is not None:
            record['scopes'] = self.scopes
        if self.tenant_ids is not None:
            record['tenantIds'] = self.tenant_ids

        return record

    def to_json(self) -> str:
        return json.dumps(self.to_record())

    def set_tenant_id(self, tenant_id: int):
        self.tenant_ids = [tenant_id]
        self.__creds = None
