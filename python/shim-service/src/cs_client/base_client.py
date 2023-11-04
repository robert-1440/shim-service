import abc
import json
from typing import Dict, Any, Optional

from bean import beans, BeanName
from cs_client.profile import Profile
from lambda_web_framework.web_exceptions import ForbiddenException, NotAuthorizedException, BadRequestException
from utils.http_client import join_base_path, HttpMethod as Method, join_paths, HttpResponse, MediaType, \
    HttpClientException, RequestBuilder, HttpClient


class BaseClient(metaclass=abc.ABCMeta):
    def __init__(self, profile: Profile, uri: str = None):
        self.profile = profile
        self.base_url = join_base_path(profile.url, "configuration-service")
        self.http_client: HttpClient = beans.get_bean_instance(BeanName.HTTP_CLIENT)
        if uri is not None:
            self.base_url = join_base_path(self.base_url, uri)

    @abc.abstractmethod
    def handle_auth(self, builder: RequestBuilder):
        raise NotImplementedError()

    def __builder(self, method: Method, uri: str) -> RequestBuilder:
        return RequestBuilder(method, join_paths(self.base_url, uri))

    def get(self, uri: str) -> HttpResponse:
        return self.__send(self.__builder(Method.GET, uri).accept(MediaType.ALL))

    def get_json(self, uri: str, headers: Dict[str, str] = None) -> Optional[Dict[str, Any]]:
        r = self.__send(self.__builder(Method.GET, uri).accept(MediaType.JSON).headers(headers))
        if r is None:
            return None
        return json.loads(r.get_body())

    def __send(self, b: RequestBuilder) -> Optional[HttpResponse]:
        self.handle_auth(b)
        try:
            return b.send(self.http_client)
        except HttpClientException as ex:
            code = ex.get_status_code()
            if code == 404:
                return None
            if code == 401:
                raise NotAuthorizedException(ex.get_body_as_string())
            if code == 403:
                raise ForbiddenException(ex.get_body_as_string())
            if code == 400:
                raise BadRequestException(ex.get_body_as_string())
            raise ex
