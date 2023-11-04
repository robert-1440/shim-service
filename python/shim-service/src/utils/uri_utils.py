from collections import namedtuple
from typing import Optional, Dict, Any, Union
from urllib.parse import urlunparse, urlencode, urlparse, parse_qsl, unquote, quote_plus

from utils.dict_utils import ReadOnlyDict
from utils.path_utils import join_paths

QueryKeyValues = Union[str, Dict[str, str]]


def _build_origin(scheme: Optional[str],
                  host: Optional[str],
                  port: Optional[str]) -> Optional[str]:
    if scheme is not None and host is not None:
        if port is not None:
            host += f':{port}'
        return f"{scheme}://{host}"
    return None


class Uri:
    def __init__(self,
                 scheme: Optional[str] = None,
                 netloc: Optional[str] = None,
                 host: Optional[str] = None,
                 port: Optional[int] = None,
                 path: Optional[str] = None,
                 query_params: Optional[QueryKeyValues] = None,
                 ):
        self.__scheme = scheme
        self.__netloc = netloc
        self.__host = host
        self.__port = port
        self.__path = path
        if query_params is not None:
            if type(query_params) is str:
                self.__query_params = query_params
            else:
                self.__query_params = ReadOnlyDict(query_params)
        else:
            self.__query_params = None
        self.__origin = _build_origin(scheme, host, port)
        self.__url: Optional[str] = None

    @property
    def scheme(self) -> Optional[str]:
        return self.__scheme

    @property
    def host(self) -> Optional[str]:
        return self.__host

    @property
    def port(self) -> Optional[int]:
        return self.__port

    @property
    def path(self) -> Optional[str]:
        return self.__path

    @property
    def query_params(self) -> Optional[Dict[str, Any]]:
        return self.__query_params

    @property
    def origin(self) -> Optional[str]:
        return self.__origin

    def to_url(self) -> str:
        if self.__url is None:
            self.__url = form_url(self.scheme, self.__netloc, self.path, self.__query_params)
        return self.__url

    def __str__(self):
        return self.to_url()

    def __repr__(self):
        return self.__str__()

    def __eq__(self, other):
        if not isinstance(other, Uri):
            return False
        return (
                self.__scheme == other.__scheme and
                self.__netloc == other.__netloc and
                self.__host == other.__host and
                self.__port == other.__port and
                self.__path == other.__path and
                self.__query_params == other.__query_params
        )

    @classmethod
    def parse(cls, uri: str):
        parsed = urlparse(uri)
        query_params = dict(parse_qsl(parsed.query)) if parsed.query else None
        path = parsed.path if len(parsed.path) > 0 else "/"
        return Uri(
            scheme=parsed.scheme,
            netloc=parsed.netloc,
            host=parsed.hostname,
            port=parsed.port,
            path=path,
            query_params=query_params
        )


def form_https_uri(host: str,
                   path: str,
                   query_params: QueryKeyValues = None) -> Uri:
    return form_uri('https', host, path, query_params=query_params)


def form_uri(scheme: str,
             host: str,
             path: str,
             query_params: Dict[str, str] = None) -> Uri:
    values = host.split(':')

    if len(values) > 1:
        port = int(values[1])
        netloc = host
        host = values[0]
    else:
        port = None
        netloc = host

    return Uri(
        scheme=scheme,
        netloc=netloc,
        host=host,
        port=port,
        path=path,
        query_params=query_params
    )


Components = namedtuple(
    typename='Components',
    field_names=['scheme', 'netloc', 'url', 'path', 'query', 'fragment']
)


def form_https_url(host: str,
                   path: str,
                   query_params: QueryKeyValues = None):
    return form_url('https', host, path, query_params=query_params)


def form_url(scheme: str,
             host: str,
             path: str,
             query_params: QueryKeyValues = None):
    if query_params is not None:
        if type(query_params) is str:
            path += f"?{query_params}"
            query_params = None
        else:
            query_params = urlencode(query_params)
    return urlunparse(Components(
        scheme=scheme,
        netloc=host,
        query=query_params,
        url=path,
        path='',
        fragment=None
    ))


def form_url_from_endpoint(
        endpoint: str,
        path: Optional[str],
        query_params: QueryKeyValues = None):
    uri = Uri.parse(endpoint)
    if path is not None:
        url = uri.origin + join_paths(uri.path, path)
    else:
        url = uri.origin
    if query_params is not None:
        url += "?"
        if type(query_params) is str:
            url += query_params
        else:
            url += urlencode(query_params)
    return url


def decode_from_url(text: str) -> str:
    return unquote(text)


def encode_query_component(text: str) -> str:
    return quote_plus(text)
