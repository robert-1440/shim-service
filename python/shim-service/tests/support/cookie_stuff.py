from http.cookiejar import Cookie
from http.cookies import SimpleCookie, Morsel
from typing import Optional, Any

from utils import date_utils


def none_if_empty(value: Optional[str], default_value: Any = None):
    if value is None or len(value) == 0:
        return default_value
    return value


def morsel_to_cookie(name: str, morsel: Morsel):
    domain: Optional[str] = morsel.get('domain')
    if domain.startswith('.'):
        domain = domain[1::]
        domain_dot = True
        domain_specified = True
    else:
        domain_dot = False
        domain_specified = len(domain) > 0

    expire_str = none_if_empty(morsel.get('expires'))
    if expire_str is not None:
        expires = date_utils.from_string(expire_str).timestamp()
    else:
        expires = None

    port = none_if_empty(morsel.get('port'))
    path = none_if_empty(morsel.get('path'))
    secure = none_if_empty(morsel.get('secure'), False)

    return Cookie(
        1,
        name,
        morsel.value,
        port=port,
        port_specified=port is not None,
        domain_specified=domain_specified,
        domain=domain,
        domain_initial_dot=domain_dot,
        path=path,
        path_specified=path is not None,
        secure=secure,
        expires=expires,
        discard=False,
        comment=None,
        comment_url=None,
        rest={}
    )


def parse_cookie(raw_value: str) -> Cookie:
    cookies = SimpleCookie(raw_value)
    for key, morsel in cookies.items():
        return morsel_to_cookie(key, morsel)
