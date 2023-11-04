import pickle
from http.cookiejar import Cookie
from io import StringIO
from typing import Optional, Callable, List

from requests.cookies import RequestsCookieJar, merge_cookies

from utils.loghelper import StandardLogger
from utils.uri_utils import Uri


def serialize_cookie_jar(jar: RequestsCookieJar) -> bytes:
    return pickle.dumps(jar._cookies)


def deserialize_to_jar(jar: RequestsCookieJar, data: bytes):
    merge_cookies(jar, pickle.loads(data))


def find_cookie_for_uri(jar: RequestsCookieJar, uri: Uri, name: str) -> Optional[str]:
    return jar.get(name, domain=uri.host, path=uri.path)


def get_all_cookies(jar: RequestsCookieJar) -> List[Cookie]:
    cookie_list = []
    for domain in jar._cookies.values():
        for path in domain.values():
            cookie_list.extend(path.values())
    return cookie_list


def get_first_cookie_match(jar: RequestsCookieJar, matcher: Callable[[Cookie], bool]) -> Optional[Cookie]:
    for domain in jar._cookies.values():
        for path in domain.values():
            for cookie in path.values():
                if matcher(cookie):
                    return cookie
    return None


def log_cookies(cookies: List[Cookie], logger: StandardLogger):
    io = StringIO()
    print("----------------------------------------------------------------------", file=io)
    print("Cookies:", file=io)
    for cookie in cookies:
        print(f"\t{cookie}", file=io)

    print("----------------------------------------------------------------------", file=io)
    logger.info(io.getvalue())
