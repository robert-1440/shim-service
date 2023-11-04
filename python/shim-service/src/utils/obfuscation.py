import base64
import hashlib
from typing import Union

from cryptography.fernet import Fernet
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC

StringOrBytes = Union[str, bytes]


def _to_bytes(data: StringOrBytes) -> bytes:
    if type(data) is str:
        return data.encode("utf-8")
    return data


class DataObfuscator:
    """
    Used to obfuscate data that can be "un-obfuscated".

    Ideal for returning tokens that a client may be storing for reference.

    THIS SHOULD NOT BE USED TO ENCRYPT SENSITIVE DATA!
    """

    def __init__(self,
                 password: StringOrBytes,
                 iv: StringOrBytes,
                 salt: StringOrBytes
                 ):
        iv = _to_bytes(iv)
        salt = _to_bytes(salt)
        password = _to_bytes(password) + iv + salt
        kdf = PBKDF2HMAC(
            algorithm=hashes.SHA256(),
            length=32,
            salt=salt,
            iterations=100
        )
        key = base64.b64encode(kdf.derive(password))
        self.__iv = hashlib.md5(iv).digest()
        self.__fernet = Fernet(key)

        # This bit of a mess: 'self.__iv[8::][::-1]' is just taking the last 8 bytes of the iv and reversing them
        self.__time = int.from_bytes(self.__iv[8::][::-1], byteorder="big")

        # _encrypt_from_parts is a private method that accepts the data, iv, and time.
        # The public methods generate a random IV, but we need to use a consistent IV to ensure consistent obfuscation
        self.__encrypter = getattr(self.__fernet, '_encrypt_from_parts')

    def obfuscate(self, data: StringOrBytes) -> bytes:
        return self.__encrypter(_to_bytes(data), self.__time, self.__iv)

    def clarify(self, data: bytes) -> bytes:
        return self.__fernet.decrypt(data)
