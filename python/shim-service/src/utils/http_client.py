import abc
import json
import os
from enum import Enum
from http.cookiejar import Cookie
from io import StringIO
from typing import Dict, Any, Union, Optional, Callable, List

import requests
from requests import Response, Session

from utils import cookie_utils
from utils.loghelper import StandardLogger
from utils.uri_utils import Uri


class HttpMethod(Enum):
    GET = 0,
    POST = 1,
    PATCH = 2
    PUT = 3,
    DELETE = 4


_MEDIA_TYPES = [
    "application/json",
    "application/x-www-form-urlencoded",
    "text/html",
    "image/jpeg",
    "image/avif",
    "application/gzip",
    "*/*"
]

HeaderValue = Union[str, int, List[str]]
Headers = Dict[str, HeaderValue]


class MediaType(Enum):
    JSON = 0
    X_WWW_FORM_URLENCODED = 1
    TEXT_HTML = 2
    IMAGE_JPEG = 3
    IMAGE_AVIF = 4
    GZIPPED = 5
    ALL = 6


class HttpResponse:
    def __init__(self, resp: Response = None,
                 status_code: int = None,
                 headers: Headers = None,
                 body: str = None,
                 raw_body: bytes = None):
        if resp is not None:
            self.status_code = resp.status_code
            self.headers = resp.headers
            self.body = resp.text
            self.raw_body = resp._content
            self.is_redirect = resp.is_redirect
        else:
            self.status_code = status_code
            self.headers = headers
            self.body = body
            self.raw_body = raw_body
            self.is_redirect = status_code // 100 == 3

    def to_string(self) -> str:
        io = StringIO()
        print(f"<<< Response >>>:\nStatus: {self.status_code}", file=io)
        if self.headers is not None and len(self.headers) > 0:
            print("Headers:", file=io)
            for key, value in self.headers.items():
                print(f"\t{key}: {value}", file=io)
            print("", file=io)
        if self.body is not None and len(self.body) > 0:
            print("Body:\n", file=io)
            print(self.body, file=io)
        print("", end="", flush=True)
        return io.getvalue()

    def is_2xx(self):
        return self.status_code // 100 == 2

    def get_status_code(self):
        return self.status_code

    def get_body(self):
        return self.body

    def get_raw_body(self) -> bytes:
        return self.raw_body

    def get_header(self, name: str) -> Optional[str]:
        return self.headers.get(name) if self.headers else None

    def get_location(self):
        return self.get_header('location')

    def get_header_as_list(self, name: str) -> Optional[List[str]]:
        if self.headers is not None:
            values = self.headers.get(name)
            if values is not None:
                if type(values) is not list:
                    return [values]
                return values

        return None


class HttpRequest:
    def __init__(self, method: HttpMethod, url: str,
                 headers: Dict[str, str] = None,
                 body: str = None,
                 follow_redirects: bool = True,
                 response_on_error: bool = False,
                 timeout_seconds: int = None):
        self.method = method
        self.url = url
        self.headers = headers
        self.body = body
        self.follow_redirects = follow_redirects
        self.__case_insensitive_headers = {}
        self.response_on_error = response_on_error
        if self.headers is not None:
            for key, value in self.headers.items():
                self.__case_insensitive_headers[key.lower()] = value
        self.timeout_seconds = timeout_seconds

    def to_string(self) -> str:
        io = StringIO()
        print(f"<<< Request >>>:\n{self.method.name} {self.url}", file=io)
        if self.headers is not None and len(self.headers) > 0:
            for key, value in self.headers.items():
                print(f"{key}: {value}", file=io)
            print("", file=io)
        if self.body is not None and len(self.body) > 0:
            print(self.body, file=io)
        return io.getvalue()

    def _send(self, session: Session,
              default_timeout: Optional[float]) -> Response:
        params = {}
        if self.headers is not None and len(self.headers) > 0:
            params['headers'] = self.headers
        if self.body is not None:
            params['data'] = self.body

        if not self.follow_redirects:
            params['allow_redirects'] = False

        timeout = self.timeout_seconds
        if timeout is None:
            timeout = default_timeout

        if timeout is not None:
            params['timeout'] = timeout

        return session.request(self.method.name, self.url, **params)

    def get_header(self, name: str) -> str:
        return self.__case_insensitive_headers.get(name.lower())


class HttpException(Exception):
    def __init__(self, r: Response):
        self.response = r

    def get_status_code(self):
        return self.response.status_code

    def is_5xx(self):
        return 500 <= self.response.status_code < 600

    def get_body_as_string(self):
        return str(self.response.text)

    def get_headers(self):
        return self.response.headers

    def __str__(self):
        message = "{}: {}".format(self.response.status_code, str(self.response.text))
        body = self.get_body_as_string()
        if body is not None and len(body) > 0:
            message += f"\n{body}"
        return message

    def __repr__(self):
        return self.__str__()


class HttpClientException(HttpException):
    def __init__(self, r):
        super().__init__(r)


class HttpServerException(HttpException):
    def __init__(self, r):
        super().__init__(r)


def _create_session():
    ca_bundle = os.environ.get("CA_BUNDLE")
    sess = requests.Session()
    if ca_bundle is not None:
        sess.verify = ca_bundle
    return sess


class HttpClient(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def set_default_timeout(self, timeout: float):
        raise NotImplementedError()

    def get(self, url: str, accept_type=MediaType.ALL,
            headers: Optional[Dict[str, HeaderValue]] = None,
            allow_redirects: bool = True,
            logger: StandardLogger = None):
        rb = RequestBuilder(HttpMethod.GET, url).accept(accept_type).allow_redirects(allow_redirects).headers(headers)
        return rb.send(self, logger=logger)

    def post(self, url: str, content_type: MediaType, accept_type=MediaType.ALL,
             body=None):
        rb = RequestBuilder(HttpMethod.POST, url).accept(accept_type).content_type(content_type).body(body)
        return rb.send(self)

    @abc.abstractmethod
    def find_first_cookie_match(self, matcher: Callable[[Cookie], bool]) -> Optional[Cookie]:
        raise NotImplementedError()

    @abc.abstractmethod
    def find_cookie_value_by_uri(self, uri: Uri, cookie_name: str) -> Optional[str]:
        raise NotImplementedError()

    @abc.abstractmethod
    def serialize_cookies(self) -> bytes:
        raise NotImplementedError()

    @abc.abstractmethod
    def add_serialized_cookies(self, data: bytes):
        raise NotImplementedError()

    @abc.abstractmethod
    def get_all_cookies(self) -> List[Cookie]:
        raise NotImplementedError()

    def log_cookies(self, logger: StandardLogger):
        cookie_utils.log_cookies(self.get_all_cookies(), logger)

    @abc.abstractmethod
    def exchange(self, req: HttpRequest) -> HttpResponse:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_session_headers(self, headers: Dict[str, str]):
        raise NotImplementedError()


class EasyCookie:
    def __init__(self, domain: str, path: str, name: str, value: str):
        self.domain = domain
        self.path = path
        self.name = name
        self.value = value


class _HttpClientImpl(HttpClient):
    def __init__(self):
        self.__session = _create_session()
        self.default_timeout = 30

    def set_default_timeout(self, timeout: float):
        self.default_timeout = timeout

    def find_first_cookie_match(self, matcher: Callable[[Cookie], bool]) -> Optional[Cookie]:
        return cookie_utils.get_first_cookie_match(self.__session.cookies, matcher)

    def add_serialized_cookies(self, data: bytes):
        cookie_utils.merge_cookies(self.__session.cookies, data)

    def find_cookie_value_by_uri(self, uri: Uri, cookie_name: str) -> Optional[str]:
        return cookie_utils.find_cookie_for_uri(self.__session.cookies, uri, cookie_name)

    def get_all_cookies(self) -> List[Cookie]:
        return cookie_utils.get_all_cookies(self.__session.cookies)

    def serialize_cookies(self) -> bytes:
        return cookie_utils.serialize_cookie_jar(self.__session.cookies)

    def set_session_headers(self, headers: Dict[str, str]):
        self.__session.headers.clear()
        self.__session.headers.update(headers)

    def exchange(self, req: HttpRequest) -> HttpResponse:
        r = req._send(self.__session, self.default_timeout)
        if not req.response_on_error:
            if not r.is_redirect or req.follow_redirects:
                _examine(r)
        return HttpResponse(r)


def _examine(r):
    if not r.ok:
        if r.status_code >= 500:
            raise HttpServerException(r)
        if r.status_code == 403:
            amzn = r.headers.get("x-amzn-ErrorType")
            if amzn is not None and amzn == "IncompleteSignatureException":
                r.status_code = 404
        raise HttpClientException(r)


def join_paths(*args) -> str:
    path = ""
    for arg in args:
        if len(path) > 0 and not path.endswith("/") and not arg.startswith("/"):
            path += "/"
        path += arg
    return path


def join_base_path(*args) -> str:
    path = join_paths(*args)
    if not path.endswith("/"):
        path += '/'
    return path


class RequestBuilder:
    def __init__(self, method: HttpMethod, uri: str):
        self.__method = method
        self.__uri = uri
        self.__headers = {}
        self.__body = None
        self.__allow_redirects = True
        self.__response_on_error = False
        self.__timeout_seconds: Optional[int] = None

    def allow_redirects(self, allow: bool):
        self.__allow_redirects = allow
        return self

    def allow_response_on_error(self, allow: bool):
        """
        Set to True to not raise an exception if !200

        :param allow: True to not raise exceptions.
        """
        self.__response_on_error = allow
        return self

    def timeout_seconds(self, seconds: int) -> 'RequestBuilder':
        self.__timeout_seconds = seconds
        return self

    def body(self, body: Any):
        if self.__method in (HttpMethod.GET, HttpMethod.DELETE):
            raise ValueError(f"Body not allowed for {self.__method}")
        if isinstance(body, dict):
            body = json.dumps(body)
        self.__body = body
        return self

    def header(self, name: str, value: HeaderValue):
        if type(value) is int:
            value = str(value)
        self.__headers[name] = value
        return self

    def headers(self, headers: Optional[Headers]):
        if headers is not None:
            for name, value in headers.items():
                self.header(name, value)
        return self

    def authorization(self, token_type: str, token: str = None):
        value = token_type
        if token is not None:
            value += f" {token}"
        return self.header('Authorization', value)

    def accept(self, media_type: MediaType):
        if media_type is not None:
            return self.header("Accept", _MEDIA_TYPES[media_type.value])
        return self

    def content_type(self, media_type: Union[MediaType, str]):
        if self.__method in (HttpMethod.GET, HttpMethod.DELETE):
            raise ValueError(f"Content-Type not allowed for {self.__method.name}")
        if isinstance(media_type, str):
            value = media_type
        else:
            value = _MEDIA_TYPES[media_type.value]
        return self.header("Content-Type", value)

    def get_uri(self) -> str:
        return self.__uri

    def get_method(self) -> HttpMethod:
        return self.__method

    def get_body(self) -> Optional[str]:
        return self.__body

    def build(self, base_url: str = None) -> HttpRequest:
        if base_url is None:
            url = self.__uri
        else:
            url = join_paths(base_url, self.__uri)
        return HttpRequest(
            self.__method,
            url,
            self.__headers,
            self.__body,
            follow_redirects=self.__allow_redirects,
            response_on_error=self.__response_on_error,
            timeout_seconds=self.__timeout_seconds
        )

    def send(self, client: HttpClient,
             base_url: str = None,
             logger: StandardLogger = None) -> HttpResponse:
        req = self.build(base_url)
        if logger is not None:
            logger.info(req.to_string())
        return client.exchange(req)


ClientBuilder = Callable[[], HttpClient]


def create_client() -> HttpClient:
    return _HttpClientImpl()


def get_client_builder() -> ClientBuilder:
    def my_builder() -> HttpClient:
        return create_client()

    return my_builder
