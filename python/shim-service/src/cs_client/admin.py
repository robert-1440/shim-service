from typing import Optional

from cs_client import AuthDetails, ConfigServiceCredentials, ConfigServiceSecret
from cs_client.base_client import BaseClient
from cs_client.profile import Profile
from lambda_web_framework.web_exceptions import NotFoundException
from utils.concurrent_cache import ConcurrentTtlCache
from utils.http_client import RequestBuilder
from utils.path_utils import encode_for_url

_CACHE_TIME_MINUTES = 10


class UserScopes:
    def __init__(self, user_id: str, scopes: str):
        self.user_id = user_id
        self.scopes = None if scopes == "*" else set(map(lambda s: s.strip(), scopes.split(",")))


class AdminClient(BaseClient):
    def __init__(self, profile: Profile):
        super(AdminClient, self).__init__(profile, uri="admin/")
        self.alias = profile.service_creds.get_id()
        self.__org_id_cache = ConcurrentTtlCache(1000,
                                                 _CACHE_TIME_MINUTES * 60,
                                                 self.__load_tenant_id)

    def handle_auth(self, builder: RequestBuilder):
        self.profile.service_creds.auth(builder)

    def __load_tenant_id(self, org_id: str) -> Optional[int]:
        return self.__find_tenant_id(org_id)

    def invalidate_org_id(self, org_id: str):
        """
        Remove the given org_id from the cache.

        :param org_id: the org id
        """
        self.__org_id_cache.invalidate(org_id)

    def get_tenant_id(self, org_id: str) -> int:
        t = self.find_tenant_id(org_id)
        if t is None:
            raise NotFoundException(f"Unable to find organization id '{org_id}'.")
        return t

    def find_tenant_id(self, org_id: str) -> Optional[int]:
        return self.__org_id_cache.get(org_id)

    def __find_tenant_id(self, org_id: str) -> Optional[int]:
        resp = self.get_json(f"organizations/{encode_for_url(org_id)}?service={self.alias}")
        if resp is None:
            return None
        return resp['tenantId']

    def find_user_scopes(self, details: AuthDetails) -> Optional[UserScopes]:
        name = self.profile.service_creds.get_id()
        resp = self.get_json(f"services/{name}/user-scopes/{details.target_id}", headers={
            "X-1440-User-Request": details.tokenize()})
        return UserScopes(details.target_id, ",".join(resp['scopes'])) if resp is not None else None

    def find_credentials(self, name: str) -> Optional[ConfigServiceCredentials]:
        service_name = self.profile.service_creds.get_id()
        resp = self.get_json(f"services/{service_name}/credentials/{encode_for_url(name)}")
        return ConfigServiceCredentials(name, resp) if resp is not None else None

    def find_secret(self, name: str) -> Optional[ConfigServiceSecret]:
        service_name = self.profile.service_creds.get_id()
        resp = self.get_json(f"services/{service_name}/secrets/{encode_for_url(name)}")
        return ConfigServiceSecret(resp) if resp is not None else None
