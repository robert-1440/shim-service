import json
import sys
from typing import Dict, Any, Type, Union, Optional, Callable, List

from lambda_web_framework.web_exceptions import NotAuthorizedException, NotFoundException, BadRequestException, \
    MissingParameterException, \
    InvalidParameterException
from utils import string_utils
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

    def assert_empty_body(self):
        if self.has_body():
            raise BadRequestException("Expected an empty body.")

    def has_body(self):
        return self.body is not None and len(self.body) > 0

    def get_body_record(self) -> Dict[str, Any]:
        if self.__body_record is None:
            self.__body_record = json.loads(self.body)
        return self.__body_record

    def get_required_body_record(self) -> Dict[str, Any]:
        return json.loads(self.get_required_body())

    def dump_headers(self) -> str:
        return json.dumps(self.headers, indent=True)

    def find_header(self, name: str):
        return self.headers.get(name)

    def get_required_header(self, name: str):
        return get_required_header(self.headers, name)

    def get_header(self, name: str) -> Optional[str]:
        return self.headers.get(name)

    def get_required_body(self) -> str:
        if self.body is None or len(self.body) == 0:
            logger.warning(f"Received empty body for {self.path}.")
            raise BadRequestException("Empty body not allowed")
        return self.body

    def get_attribute(self, key: str) -> Optional[Any]:
        return self.__attributes.get(key)

    def set_attribute(self, key: str, value: Any):
        self.__attributes[key] = value

    def invoke_attribute_as_function(self, key: str, *args) -> Any:
        v = self.__attributes.get(key)
        assert callable(v)
        return v(*args)


BodyTransformer = Callable[[LambdaHttpRequest], Any]


def get_or_not_found(event: Dict[str, Any],
                     parameter_name: str,
                     expected_type: Type):
    try:
        return get_required_parameter(event, parameter_name, expected_type)
    except Exception as ex:
        print(f"Error extracting '{parameter_name}': {ex}", file=sys.stderr)
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
        raise BadRequestException(f"'{parameter_name}' cannot be empty")
    return v


def from_json(data: Union[dict, str]) -> Dict[str, Any]:
    if type(data) is dict:
        return data
    try:
        return json.loads(data)
    except Exception:
        raise BadRequestException("Malformed JSON")


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

    @classmethod
    def created(cls, body: Any):
        return LambdaHttpResponse(201, body)


class ParameterCollector:

    def __setattr__(self, key, value):
        self.__dict__[key] = value

    def apply_to(self, target: Union[dict, Any], include_nulls: bool = False):
        if not isinstance(target, dict):
            target = target.__dict__

        for key, value in self.__dict__.items():
            if include_nulls or value is not None:
                target[key] = value

    def to_dict(self):
        return dict(self.__dict__)

    def __len__(self):
        return len(self.__dict__)

    def prune(self):
        """
        Removes all keys that have values of None.
        """
        for key in list(self.__dict__.keys()):
            v = self.__dict__[key]
            if v is None:
                del self.__dict__[key]

    def assert_not_empty(self, strip_none: bool = True):
        if self.is_empty(strip_none=strip_none):
            raise BadRequestException(f"Empty body.")

    def is_empty(self, strip_none: bool = True) -> bool:
        if len(self) == 0:
            return True
        if not strip_none:
            return False
        for _ in filter(lambda v: v is not None, self.__dict__.values()):
            return False
        return True


def to_int(value: str, parameter_name: str) -> int:
    try:
        return int(value)
    except Exception:
        raise BadRequestException(f"{parameter_name}: '{value}' is not a valid integer.")


class ParameterGetter:
    def __init__(self, path: Optional[str], node: dict):
        self.path = path
        self.node = dict(node)

    def as_dict(self):
        n = dict(self.node)
        self.node.clear()
        return n

    def __consruct_child(self, name: str, node: dict):
        if self.path is None:
            path = ""
        else:
            path = f"{self.path}/"
        return ParameterGetter(path + name, node)

    def assert_empty(self):
        self.__wrap(lambda: assert_empty(self.node))

    def get_required_child(self, name: str) -> Optional:
        return self.__get_child(name, lambda n: self.get_required_parameter(name, expected_type=dict))

    def get_child(self, name: str) -> Optional:
        return self.__get_child(name, lambda n: self.get_parameter(name, expected_type=dict))

    def __get_child(self, name: str, getter: Callable[[str], Any]):
        node = getter(name)
        if node is not None:
            v = self.__consruct_child(name, node)
            return v
        return None

    def process_required_child(self, name: str, caller: Callable) -> Any:
        return self.__process(name, self.get_required_child, caller)

    def process_child(self, name: str, caller: Callable) -> Any:
        return self.__process(name, self.get_child, caller)

    def __process(self, name: str, getter: Callable[[str], Any], caller: Callable) -> Any:
        g = getter(name)
        if g is not None:
            v = caller(g)
            g.assert_empty()
            return v
        return None

    def __create_child(self, name: str, node: dict, caller: Callable):
        getter = self.__consruct_child(name, node)
        v = caller(getter)
        getter.assert_empty()
        return v

    def get_required_string(self, name: str) -> str:
        return self.get_required_parameter(name, str)

    def get_required_string_or_bytes(self, name: str,
                                     strict: bool = False,
                                     is_base64: bool = False) -> str:
        v = self.get_required_parameter(name, Any)
        t = type(v)
        if t is not str:
            if strict:
                self.__throw(InvalidParameterException, f"Expected '{name}' to be a string.")
            if t is bool:
                return string_utils.to_json_string(v)
            v = str(v)

        return self.__translate_content(name, v, is_base64)

    def process_child_list(self, name: str, initializer: Callable[[Any], Any]) -> Optional[List[Any]]:
        child_list = self.get_parameter(name, list)
        if child_list is None:
            return None
        translated = []
        for child in child_list:
            our_name = f"{name}[{len(translated)}]"
            if not isinstance(child, dict):
                raise self.__throw(InvalidParameterException, f"Expected '{our_name}' to be a map.")
            translated.append(self.__create_child(our_name, child, initializer))
        return translated

    def get_string(self, name: str, default_value: str = None) -> Optional[str]:
        return self.get_parameter(name, str) or default_value

    def get_parameter(self,
                      parameter_name: str,
                      expected_type: Type,
                      remove: bool = True,
                      none_if_empty: bool = False,
                      none_ok: bool = True) -> Any:
        return self.__wrap(lambda: get_parameter(
            self.node,
            parameter_name,
            expected_type,
            remove,
            none_if_empty,
            none_ok
        ))

    def get_required_parameter(self,
                               parameter_name: str,
                               expected_type: Type,
                               parameter_type: str = "parameter",
                               remove: bool = True,
                               empty_ok: bool = False) -> Any:
        return self.__wrap(lambda: get_required_parameter(
            self.node,
            parameter_name,
            expected_type,
            parameter_type,
            remove,
            empty_ok
        ))

    def __wrap(self, caller: Callable):
        try:
            return caller()
        except BadRequestException as ex:
            raise self.__rethrow(ex)

    def __rethrow(self, ex: BadRequestException):
        if self.path is not None:
            t = type(ex)
            raise t(f"In {self.path} - {ex.message}")

        raise ex

    def __throw(self, exception_type: Type[Exception], message: str, name: str = None):
        if self.path is not None:
            message = f"In {self.path} - {message}"
        if name is None:
            raise exception_type(message)
        else:
            raise exception_type(name, message)

    def get_required_boolean(self, name: str) -> bool:
        b = self.get_boolean(name)
        if b is None:
            raise self.__throw(MissingParameterException, "Missing required parameter", name)
        return b

    def get_boolean(self, name: str, default_value: bool = None) -> Optional[bool]:
        v = self.node.pop(name, None)
        if v is None:
            return default_value
        if type(v) is bool:
            return v
        if type(v) is str:
            v = v.lower()
            if v == 'true':
                return True
            if v == 'false':
                return False

        self.__throw(InvalidParameterException, f"Expecting a boolean type for {name}, got '{v}'.",
                     name=name)

    def __translate_content(self, name: str, content: Any, is_base64: bool):
        if is_base64:
            content = string_utils.decode_base64_to_bytes(content, fail_on_error=False)
            if content is None:
                self.__throw(InvalidParameterException, f"'{name}' is not valid base64.",
                             name=name)
        return content
