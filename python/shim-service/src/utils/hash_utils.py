import hashlib
import hmac
from typing import Union

from utils.string_utils import encode_to_base64string

StringOrBytes = Union[str, bytes]


def hmac_sha256(data: StringOrBytes, key: StringOrBytes) -> bytes:
    if type(data) is str:
        data = data.encode("utf-8")
    if type(key) is str:
        key = key.encode("utf-8")
    return hmac.new(key, data, hashlib.sha256).digest()


def hmac_sha256_to_hex(data: StringOrBytes, key: StringOrBytes) -> str:
    return hmac_sha256(data, key).hex()


def hmac_sha256_to_base64(data: StringOrBytes, key: StringOrBytes) -> str:
    return encode_to_base64string(hmac_sha256(data, key))


def hash_sha256_to_hex(data: StringOrBytes) -> str:
    if type(data) is str:
        data = data.encode("utf-8")
    m = hashlib.sha256(data)
    return m.digest().hex()


def hash_sha512_to_hex(data: StringOrBytes) -> str:
    if type(data) is str:
        data = data.encode("utf-8")
    m = hashlib.sha512(data)
    return m.digest().hex()


