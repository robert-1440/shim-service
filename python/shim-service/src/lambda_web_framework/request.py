import json
import sys
from typing import Dict, Any, Type, Union, Optional, Callable

from lambda_web_framework.web_exceptions import NotAuthorizedException, NotFoundException, BadRequestException, \
    MissingParameterException, \
    InvalidParameterException
from utils.loghelper import get_logger

logger = get_logger(__name__)


class LambdaHttpRequest:
    headers: dict[str, Any]
    method: str
    source_ip: str
    path: str
    __body_record: Optional[Dict[str, Any]]

    def __init__(self, event: Dict[str, Any]):
        if "rawPath" in event:
            self.path = event['rawPath']
            request_context = get_or_not_found(event, "requestContext", dict)
            http = get_or_not_found(request_context, "http", dict)
            self.source_ip = get_or_not_found(http, "sourceIp", str)
            self.method = get_or_not_found(http, "method", str)
            self.headers = get_required_parameter(event, "headers", dict)
        else:
            self.path = get_or_not_found(event, 'path', str)
            self.method = get_or_not_found(event, "httpMethod", str)
            request_context = get_or_not_found(event, "requestContext", dict)
            self.path = request_context.get('path', self.path)
            identity = get_or_not_found(request_context, "identity", dict)
            self.source_ip = get_or_not_found(identity, "sourceIp", str)
            headers = get_required_parameter(event, "headers", dict)
            self.headers = {}
            for key, value in headers.items():
                self.headers[key.lower()] = value

        self.body: Optional[str] = event.get('body')
        self.__body_record = None
        self.query_string_parameters: Optional[Dict[str, str]] = event.get('queryStringParameters')

        self.__attributes = {}

    def set_credentials(self, creds: Any):
        self.__attributes['creds'] = creds

    def get_credentials(self) -> Any:
        return self.__attributes['creds']

    def set_session(self, session: Any):
        self.__attributes['session'] = session

    def get_session(self):
        return self.__attributes['session']

    def get_required_header(self, name: str):
        return get_required_header(self.headers, name)

    def get_header(self, name: str) -> Optional[str]:
        return self.headers.get(name)

    def get_attribute(self, key: str) -> Optional[Any]:
        return self.__attributes.get(key)

    def set_attribute(self, key: str, value: Any):
        self.__attributes[key] = value

    def set_params(self, params: dict):
        self.set_attribute("params", params)

    def get_params(self) -> dict:
        v = self.get_attribute("params")
        return v or {}

    def get_url_parameter(self, name: str) -> str:
        return self.get_params().get(name)

    @classmethod
    def is_web_event(cls, event: Dict[str, Any]):
        return "rawPath" in event or "path" in event


BodyTransformer = Callable[[LambdaHttpRequest], Any]


def get_or_not_found(event: Dict[str, Any],
                     parameter_name: str,
                     expected_type: Type):
    try:
        return get_required_parameter(event, parameter_name, expected_type)
    except Exception as ex:
        logger.warning(f"Error extracting '{parameter_name}': {ex}", file=sys.stderr)
        raise NotFoundException()


def get_or_auth_fail(event: Dict[str, Any],
                     parameter_name: str,
                     expected_type: Type,
                     parameter_type: str = "parameter"):
    try:
        return get_required_parameter(event, parameter_name, expected_type,
                                      parameter_type=parameter_type)
    except Exception as ex:
        raise NotAuthorizedException(f"{ex}")


__NULL = object()


def assert_empty(event: Dict[str, Any]):
    if len(event) != 0:
        raise BadRequestException(f"The following properties are not recognized: {','.join(event.keys())}.")


def get_parameter(event: Dict[str, Any],
                  parameter_name: str,
                  expected_type: Type,
                  remove: bool = False,
                  none_if_empty: bool = False,
                  none_ok: bool = True,
                  max_length: int = None) -> Any:
    v = event.get(parameter_name, __NULL) if not remove else event.pop(parameter_name, __NULL)
    if id(v) == id(__NULL):
        return None
    if v is None:
        if not none_ok:
            raise InvalidParameterException(parameter_name, "parameter cannot be null.")
        return None
    if expected_type is Any:
        return v
    t = type(v)
    if t is not expected_type:
        raise InvalidParameterException(parameter_name, "invalid type.")
    if t is str:
        v: Optional[str]
        if none_if_empty:
            v = v.strip()
            if len(v) == 0:
                if not none_ok:
                    raise InvalidParameterException(parameter_name, "value cannot be empty.")
                v = None
        if v is not None and max_length is not None:
            if len(v) > max_length:
                raise InvalidParameterException(parameter_name,
                                                f"length of {len(v)} exceeds maximum allowed of {max_length}.")
    return v


def get_required_header(event: Dict[str, Any],
                        header_name: str):
    return get_required_parameter(event, header_name, str, parameter_type="header")


def get_required_parameter(event: Dict[str, Any],
                           parameter_name: str,
                           expected_type: Type,
                           parameter_type: str = "parameter",
                           remove: bool = False,
                           empty_ok: bool = False,
                           max_length: int = None) -> Any:
    use_name = parameter_name if parameter_type != 'header' else parameter_name.lower()
    v = get_parameter(event, use_name, expected_type, remove=remove, max_length=max_length)
    if v is None:
        raise MissingParameterException(parameter_name, parameter_type=parameter_type)
    if not empty_ok and expected_type == str and len(v) == 0:
        raise BadRequestException(f"'{parameter_name}' cannot be empty.")
    return v


def from_json(data: Union[dict, str]) -> Dict[str, Any]:
    if type(data) is dict:
        return data
    try:
        return json.loads(data)
    except Exception:
        logger.info(f"Invalid JSON: <<<{data}>>>")
        raise BadRequestException("Malformed JSON.")


class LambdaHttpResponse:
    def __init__(self, code: int, body: Any = None, headers: Dict[str, str] = None):
        self.code = code
        self.body = body
        self.headers = headers

    def to_dict(self) -> Dict[str, Any]:
        record = {'statusCode': self.code}
        if self.body is not None:
            record['body'] = self.body
        if self.headers is not None:
            record['headers'] = self.headers
        return record

    @classmethod
    def ok(cls, body: Any = None):
        return LambdaHttpResponse(200, body)

    @classmethod
    def no_content(cls):
        return LambdaHttpResponse(204)
