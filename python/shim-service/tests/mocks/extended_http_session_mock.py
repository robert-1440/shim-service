import base64
import json
import sys
import urllib.parse
from copy import copy
from typing import Dict, Optional, Any

from cs_client import ServiceKeyCredentials
from lambda_web_framework.request import get_required_parameter, get_or_auth_fail
from lambda_web_framework.web_exceptions import NotAuthorizedException, BadRequestException
from mocks.http_session_mock import MockHttpSession, MockedResponse
from repos.secrets import ServiceKeys, ServiceKey
from support.credentials import TestCredentials
from support.secrets import TestSecret
from utils import path_utils, date_utils
from utils.http_client import HttpMethod, HttpRequest
from utils.path_utils import Path


def _extract_auth(headers: Dict[str, Any]) -> int:
    auth = headers.get('Authorization')
    if auth is None:
        raise NotAuthorizedException("No 'Authorization' header.")
    values = auth.split(" ")
    if len(values) == 2:
        if values[0] == "1440-HMAC-SHA256" and values[1].isdigit():
            stamp = int(values[1])
            age = date_utils.get_age_in_seconds(stamp)
            if abs(age) > 60:
                print(f"Request time age is {age} seconds.")
            else:
                return stamp
    print(f"Invalid auth header: {auth}", file=sys.stderr)
    raise NotAuthorizedException("Invalid Authorization header.")


def _extract_service_creds(keys: ServiceKeys, value: str) -> ServiceKeyCredentials:
    decoded = base64.b64decode(value).decode('utf-8')
    values = decoded.split("\t")
    if len(values) == 2 and values[0] == 'shim':
        key: ServiceKey = next(filter(lambda k: k.key_id == values[1], keys.keys))
        return ServiceKeyCredentials(values[0], key)
    print(f"X-1440-Service-Key header is invalid: {value}.", file=sys.stderr)
    raise BadRequestException("Invalid X-1440-Service-Key header")


def _validate_service_key(keys: ServiceKeys, request: HttpRequest):
    request_time = _extract_auth(request.headers)
    sig = get_or_auth_fail(request.headers, "X-1440-Signature", str)

    encoded = get_required_parameter(request.headers, 'X-1440-Service-Key', str)
    creds = _extract_service_creds(keys, encoded)
    path = path_utils.get_path(request.url)
    sig_string, expected_sig = creds.sign(path, request.method.name, request_time, request.body)
    if sig != expected_sig:
        print(f"Signature does not match. Signing string is {sig_string}", file=sys.stderr)
        raise NotAuthorizedException("x-1440-signature header is incorrect.")
    return path


_GET_CREDS_PATH = Path("/configuration-service/admin/services/{service}/credentials/{credsName}")
_GET_SECRET_PATH = Path("/configuration-service/admin/services/{service}/secrets/{secretName}")
_LOOKUP_TENANT_ID_PATH = Path("/configuration-service/admin/organizations/{orgId}")


class ExtendedHttpMockSession(MockHttpSession):

    def __init__(self):
        super(ExtendedHttpMockSession, self).__init__()
        self.credentials: Dict[str, TestCredentials] = {}
        self.service_keys: Optional[ServiceKeys] = None
        self.tenants: Dict[str, int] = {}
        self.secrets: Dict[str, TestSecret] = {}

    def add_tenant(self, org_id: str, tenant_id: int):
        self.tenants[org_id] = tenant_id

    def add_secret(self, name: str, secret_value: str):
        self.secrets[name] = TestSecret(name, secret_value)

    def set_service_keys(self, keys: ServiceKeys):
        self.service_keys = keys

    def __lookup_tenant(self, record: dict, request: HttpRequest) -> MockedResponse:
        org_id = record['orgId']
        query = urllib.parse.urlparse(request.url).query
        if query is None:
            return MockedResponse(400, body="No service specified")
        record = path_utils.parse_query_string(query)

        service = record['service']
        if service != 'shim':
            return MockedResponse(403, body=f"Not approved for {service}.")
        t = self.tenants.get(org_id)
        if t is None:
            return MockedResponse(404, body=f"Unable to find tenant with org id {org_id}.")
        return MockedResponse(200, body=json.dumps({'tenantId': t}))

    def __get_creds(self, record: dict) -> MockedResponse:
        service = record['service']
        if service != 'shim':
            raise BadRequestException(f"Invalid service {service}.")
        creds = self.credentials.get(record['credsName'])
        if creds is None:
            return MockedResponse(404, body="Creds not found")
        return MockedResponse(200, body=creds.to_json())

    def __find_secret(self, query_params: dict):
        secret_name = query_params['secretName']
        secret = self.secrets.get(secret_name)
        if secret is None:
            return MockedResponse(404, body="Secret not found")
        return MockedResponse(200, body=json.dumps(secret.to_config_service_secret().to_record()))

    def __handle_config_service_call(self, request: HttpRequest) -> MockedResponse:
        path = _validate_service_key(self.service_keys, request)
        result = _GET_CREDS_PATH.matches(path)
        if result is not None:
            return self.__get_creds(result)
        result = _LOOKUP_TENANT_ID_PATH.matches(path)
        if result is not None:
            return self.__lookup_tenant(result, request)
        result = _GET_SECRET_PATH.matches(path)
        if result is not None:
            return self.__find_secret(result)

        raise NotImplementedError(f"mock not implemented for: {path}")

    def check_for_response(self, request: HttpRequest) -> MockedResponse:
        if request.method == HttpMethod.GET:
            path = path_utils.get_path(request.url)
            if path.startswith("/configuration-service/"):
                return self.__handle_config_service_call(request)
        return super().check_for_response(request)

    def add_credentials(self, credentials: TestCredentials):
        self.credentials[credentials.name] = copy(credentials)
