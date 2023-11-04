import base64
import uuid as sys_uuid
import zlib
from _decimal import Decimal
from typing import Optional, Union, Any, Pattern, Type


def decode_base64_to_string(value: Optional[str], fail_on_error: bool = True) -> Optional[str]:
    return __decode_base64(value, str, fail_on_error=fail_on_error)


def decode_urlsafe_base64_to_string(value: Optional[str], fail_on_error: bool = True) -> Optional[str]:
    if value is None:
        return value
    try:
        return str(base64.urlsafe_b64decode(value), "utf-8")
    except Exception as ex:
        if fail_on_error:
            raise ex
    return None


def decode_base64_to_bytes(value: Optional[str], fail_on_error: bool = True) -> Optional[bytes]:
    return __decode_base64(value, bytes, fail_on_error=fail_on_error)


def __decode_base64(value: Optional[str],
                    result_type: Type,
                    fail_on_error: bool = True) -> Optional[Union[str, bytes]]:
    if value is None:
        return None
    try:
        b = base64.b64decode(value, validate=True)
        return b if result_type == bytes else b.decode('utf-8')
    except Exception as ex:
        if fail_on_error:
            raise ex
    return None


def encode_to_base64string(value: Union[str, bytes]) -> str:
    """
    Encodes the given string or bytes to a base64 string.

    :param value: the value to encode.
    :return: base64-encoded string.
    """
    if type(value) is str:
        value = value.encode("utf-8")
    string_value = str(base64.b64encode(value), "utf-8")
    return string_value


def encode_to_urlsafe_base64string(value: Union[str, bytes]) -> str:
    if type(value) is str:
        value = value.encode("utf-8")
    string_value = str(base64.urlsafe_b64encode(value), "utf-8")
    return string_value


_KNOWN_TYPES = {int, float, bool, Decimal}


def to_json_string(obj: Any) -> str:
    if obj is None:
        return 'null'
    t = type(obj)
    if t == str:
        return obj
    if t not in _KNOWN_TYPES:
        raise ValueError(f"Unsupported type: {t} ({obj})")
    if t == bool:
        return "true" if obj else "false"
    return str(obj)


def uuid() -> str:
    """
    Generates a UUID string.

    :return: string that is the UUID.
    """
    return str(sys_uuid.uuid4())


def get_regex_match(pattern: Pattern, string: str, group: int = 0):
    match = pattern.search(string)
    if match is not None:
        return match[group]
    return None


def compress(s: str) -> bytes:
    return zlib.compress(s.encode('utf-8'))


def decompress(data: Optional[bytes]) -> Optional[str]:
    if data is None:
        return None
    inflated = zlib.decompress(data)
    return inflated.decode("utf-8")
