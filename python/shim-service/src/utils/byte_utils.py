import zlib
from typing import Optional

EMPTY_BYTES = b''


def compress(data: Optional[bytes]) -> Optional[bytes]:
    return zlib.compress(data) if data is not None and len(data) > 0 else data


def decompress(data: Optional[bytes]) -> Optional[bytes]:
    return zlib.decompress(data) if data is not None and len(data) > 0 else data
