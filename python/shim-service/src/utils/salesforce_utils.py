import re
from functools import reduce
from typing import Optional

from utils.http_client import HttpClient
from utils.string_utils import get_regex_match
from utils.uri_utils import Uri, decode_from_url

_AURA_TOKEN_REGEX = re.compile(r'([A-Za-z0-9_-]+={0,2})\.\.([A-Za-z0-9_-]+={0,2})$')
_AURA_FRAMEWORK_ID_REGEX = re.compile(r'/auraFW/javascript/(.*?)/aura_')
_AURA_CONTEXT_REGEX = re.compile(r'</l/(.*?)/app\.css')


def extract_sf_sub_domain(uri: Uri):
    def get_sf_domain(previous: Optional[str], element: str):
        if element == 'develop':
            return f"{previous}.{element}"
        return previous

    return reduce(get_sf_domain, uri.host.split('.'))


def extract_aura_token(client: HttpClient) -> Optional[str]:
    cookie = client.find_first_cookie_match(lambda cookie: get_regex_match(_AURA_TOKEN_REGEX, cookie.value))
    return cookie.value if cookie is not None else None


def extract_aura_framework_id(link: str) -> Optional[str]:
    return get_regex_match(_AURA_FRAMEWORK_ID_REGEX, link, 1)


def extract_aura_context_json(link: str) -> Optional[str]:
    match = get_regex_match(_AURA_CONTEXT_REGEX, link, 1)
    if match is not None:
        return decode_from_url(match)
    return None
