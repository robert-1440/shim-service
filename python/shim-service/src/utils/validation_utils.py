import re
import urllib.parse
from re import Pattern
from typing import Dict, Any, Union

from instance import Instance
from lambda_web_framework.request import get_required_parameter
from lambda_web_framework.web_exceptions import BadRequestException, InvalidParameterException
from lambda_web_framework.web_router import LambdaHttpRequest
from utils import loghelper

__REQUEST_ID_REGEX = re.compile(r"^[a-zA-Z0-9-]+$")

__USER_ID_REGEX = re.compile(r'^005[a-zA-Z0-9]{15,18}')

__WORK_ID_REGEX = re.compile(r'^0Bz[a-zA-Z0-9]{12,15}')

__WORK_TARGET_ID_REGEX = re.compile(r'^0Mw[a-zA-Z0-9]{12,15}')

logger = loghelper.get_logger(__name__)


def assert_valid_event_id(event_id: str):
    if re.match(__REQUEST_ID_REGEX, event_id) is None:
        raise BadRequestException("Malformed event id")


def __get_with_regex(body: Dict[str, Any], key: str, regex: Union[str, Pattern],
                     max_length: int = None) -> str:
    value = get_required_parameter(body, key, str, remove=True)
    if re.match(regex, value) is None:
        raise InvalidParameterException(key,
                                        f"value '{value}' is "
                                        f"malformed - regex='{regex.pattern}'.")
    if max_length is not None and len(value) > max_length:
        raise InvalidParameterException(key,
                                        f"value '{value}' exceeds the maximum allowed size of {max_length}.")
    return value


def get_url(body: Dict[str, Any], key: str) -> str:
    url = get_required_parameter(body, key, str, remove=True)
    try:
        parsed = urllib.parse.urlparse(url)
    except Exception as ex:
        logger.warning(f"Invalid url for {key}: {url} ({ex}).")
        raise BadRequestException(f"{key} value of '{url}' is not a valid URL.")
    if parsed.scheme is None or parsed.scheme != 'https':
        raise BadRequestException(f"{key}: Only URLs with https are allowed. URL is {url}")
    return url


def get_user_id(body: Dict[str, Any], key: str = "userId") -> str:
    return __get_with_regex(body, key, __USER_ID_REGEX)


def get_work_id(body: Dict[str, Any], key: str = "workId") -> str:
    return __get_with_regex(body, key, __WORK_ID_REGEX)


def get_work_target_id(body: Dict[str, Any], key: str = "workTargetId") -> str:
    return __get_with_regex(body, key, __WORK_TARGET_ID_REGEX)


def get_tenant_id(instance: Instance, request: LambdaHttpRequest, org_id: str) -> int:
    tenant_id = instance.get_tenant_id(org_id)
    request.get_credentials().assert_tenant_access(tenant_id)
    return tenant_id
