import abc
from enum import Enum
from typing import Callable, Collection, Optional, List, Dict, Any

from lambda_web_framework.request import LambdaHttpRequest, LambdaHttpResponse, BodyTransformer
from lambda_web_framework.web_exceptions import LambdaHttpException
from services.sfdc.live_agent.omnichannel_api import load_api
from utils.http_client import HttpException
from utils.path_utils import Path


class Method(Enum):
    GET = 0,
    POST = 1,
    PATCH = 2
    PUT = 3,
    DELETE = 4

    def body_allowed(self):
        return self == Method.POST or self == Method.PATCH or self == Method.PUT


class Route:
    def __init__(self, path: str, method: Method, caller: Callable,
                 response_codes: Collection[int],
                 include_request: bool,
                 session_required: bool,
                 api_required: bool,
                 no_instance: bool,
                 body_transformer: BodyTransformer):
        self.no_instance = no_instance
        self.has_query_params = path.endswith("?")
        if self.has_query_params:
            path = path[0:len(path) - 1:]
        self.path = path
        self.match_path = Path(path)
        self.method = method
        self.caller = caller
        self.response_codes = response_codes
        self.include_request = include_request
        self.session_required = session_required
        self.api_required = api_required
        self.body_transformer = body_transformer

    def path_matches(self, path: str, parts: Optional[List[str]] = None) -> Dict[str, str]:
        return self.match_path.matches(path, parts)

    def __invoke_api(self, request: LambdaHttpRequest, args: list, params: dict):
        with load_api(request.get_session()) as api:
            args.append(api)
            try:
                return self.caller(*args, **params)
            except HttpException as ex:
                body = {
                    'statusCode': ex.get_status_code(),
                    'body': ex.get_body_as_string()
                }
                raise LambdaHttpException(502, "SF call failed.", body=body)

    def invoke(self, instance: Any,
               request: LambdaHttpRequest,
               params: Dict[str, Any]) -> LambdaHttpResponse:
        include_request = self.include_request
        args = [instance] if not self.no_instance else []

        if self.body_transformer is not None:
            request.set_params(params)
            params = {}
            args.append(self.body_transformer(request))
        else:
            if include_request or self.method.body_allowed():
                args.append(request)

        if self.session_required:
            args.append(request.get_session())

        if self.api_required:
            return self.__invoke_api(request, args, params)

        return self.caller(*args, **params)


class Authenticator(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def authenticate(self, route: Route, request: LambdaHttpRequest):
        raise NotImplementedError()

    @abc.abstractmethod
    def clear_cache(self):
        raise NotImplementedError()
