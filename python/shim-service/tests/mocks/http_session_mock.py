import json
from typing import List, Dict, Optional, Union, Callable

from requests.cookies import RequestsCookieJar

from support.cookie_stuff import parse_cookie
from utils import cookie_utils
from utils.http_client import HttpRequest, HttpMethod, Headers
from utils.uri_utils import Uri

RequestCallback = Optional[Callable[[HttpRequest], Optional['MockedResponse']]]


class MockedResponse:
    def __init__(self, status_code: int,
                 headers: Dict[str, str] = None,
                 body: str = None,
                 expected_content_type: str = None,
                 expected_headers: Headers = None,
                 request_callback: RequestCallback = None):
        self.status_code = status_code
        self.headers = headers
        self.body = body
        self.url: Optional[str] = None
        self.cookies: Optional[Dict[str, str]] = None
        self.is_redirect = status_code // 100 == 3
        self.expected_content_type = expected_content_type
        self.expected_headers = expected_headers
        self.request_callback = request_callback

    def validate(self, request: HttpRequest):
        if self.expected_content_type is not None:
            actual = request.get_header('content-type')
            if actual != self.expected_content_type:
                return MockedResponse(415, body=f"Expected content type of "
                                                f"{self.expected_content_type} vs {actual}.")

        if self.expected_headers is not None:
            for header, value in self.expected_headers.items():
                req_value = request.get_header(header)
                if req_value is None:
                    raise AssertionError(f"Header '{header}' was expected in request, but was not present.")
                if req_value != value:
                    raise AssertionError(f"Expected header '{header}' to be '{value}', but was '{req_value}.")
        if self.request_callback is not None:
            return self.request_callback(request)
        return None


class SimulatedResponse:
    def __init__(self, source: MockedResponse):
        self.status_code = source.status_code
        self.ok = source.status_code // 100 == 2
        self.text = source.body
        self.raw = source.body
        self._content = source.body
        self.headers = source.headers
        self.is_redirect = source.status_code // 100 == 3


METHOD_MAP = {
    'GET': HttpMethod.GET,
    'POST': HttpMethod.POST,
    'PUT': HttpMethod.PUT,
    'PATCH': HttpMethod.PATCH,
    'DELETE': HttpMethod.DELETE
}


class MockHttpSession:
    def __init__(self):
        self.requests_seen: List[HttpRequest] = []
        self.responses: Dict[str, List[MockedResponse]] = {}
        self.cookies = RequestsCookieJar()
        self.capture_only = False

    def add_serialized_cookies(self, data: bytes):
        cookie_utils.deserialize_to_jar(self.cookies, data)

    def find_cookie_by_uri(self, uri: Uri, cookie_name: str) -> Optional[str]:
        return cookie_utils.find_cookie_for_uri(self.cookies, uri, cookie_name)

    def get_cookies(self) -> Dict[str, str]:
        return dict(self.cookies)

    def serialize_cookies(self) -> bytes:
        return cookie_utils.serialize_cookie_jar(self.cookies)

    def add_post_response(self,
                          url: str,
                          status_code: int,
                          headers: Dict[str, Union[str, List[str]]] = None,
                          body: str = None,
                          expected_content_type: str = None,
                          expected_headers: Optional[Headers] = None,
                          request_callback: RequestCallback = None
                          ):
        self.add_response("POST", url, status_code, headers=headers, body=body,
                          expected_content_type=expected_content_type,
                          expected_headers=expected_headers,
                          request_callback=request_callback)

    def add_get_response(self,
                         url: str,
                         status_code: int,
                         headers: Dict[str, Union[str, List[str]]] = None,
                         cookies: Dict[str, str] = None,
                         body=None,
                         expected_headers: Optional[Headers] = None,
                         request_callback: RequestCallback = None):
        self.add_response("GET", url, status_code, headers=headers, cookies=cookies,
                          body=body,
                          expected_headers=expected_headers,
                          request_callback=request_callback)

    def add_response(self,
                     method: str,
                     url: str,
                     status_code: int,
                     headers: Dict[str, Union[str, List[str]]] = None,
                     body: Union[str, dict] = None,
                     cookies: Dict[str, str] = None,
                     expected_content_type: str = None,
                     expected_headers: Optional[Headers] = None,
                     request_callback: RequestCallback = None
                     ):
        if isinstance(body, dict):
            body = json.dumps(body)
        r = MockedResponse(status_code, headers=headers, body=body,
                           expected_content_type=expected_content_type,
                           expected_headers=expected_headers,
                           request_callback=request_callback)
        key = f"{method}:{url}"
        responses = self.responses.get(key)
        if responses is None:
            self.responses[key] = responses = []
        r.url = url
        r.cookies = cookies
        responses.append(r)

    def reset(self):
        self.requests_seen.clear()
        self.responses.clear()

    def assert_no_requests(self):
        assert len(self.requests_seen) == 0

    def pop_request(self):
        return self.requests_seen.pop(0)

    def __check_for_cookies(self, req: HttpRequest, resp: MockedResponse):
        if resp.cookies is not None:
            for name, value in resp.cookies.items():
                cookie = parse_cookie(f"{name}={value}")
                if not cookie.domain_specified:
                    cookie.domain = Uri.parse(req.url).host
                if cookie.path is None:
                    cookie.path = "/"
                self.cookies.set_cookie(cookie)

    def check_for_response(self, request: HttpRequest) -> MockedResponse:
        key = f"{request.method.name}:{request.url}"
        r = self.responses.get(key)
        if r is None:
            responses = ",\n".join(self.responses.keys())
            raise AssertionError(f"Unexpected request: {request.method.name} {request.url}. "
                                 f"Available responses:\n{responses}")
        if len(r) == 1:
            resp = r[0]
        else:
            resp = r.pop(0)
        bad_resp = resp.validate(request)
        if bad_resp is not None:
            return bad_resp
        self.__check_for_cookies(request, resp)
        return resp

    def request(self, method: str, url: str, **kwargs) -> SimulatedResponse:
        data = kwargs.pop('data', None)
        headers: Optional[Dict[str, List[str]]] = kwargs.pop('headers', None)
        allow_redirects: bool = kwargs.pop('allow_redirects', False)
        req = HttpRequest(
            METHOD_MAP[method.upper()],
            url,
            headers,
            body=data,
            follow_redirects=allow_redirects,
        timeout_seconds=kwargs.pop('timeout', None))
        self.requests_seen.append(req)
        if self.capture_only:
            return SimulatedResponse(MockedResponse(200))
        resp = self.check_for_response(req)
        return SimulatedResponse(resp)
