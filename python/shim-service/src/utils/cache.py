import time
from threading import RLock
from typing import Dict, Any, Tuple, Optional, Callable

__global_mutex = RLock()


class TTLCache:
    def __init__(self, maxsize: int, ttl: float):
        assert maxsize > 1
        self.__maxsize = maxsize
        assert ttl > 0
        self.__ttl_seconds = ttl
        self.__cache: Dict[Any, Tuple[float, Any]] = {}
        self.__mutex = RLock()

    def get(self, key: Any, loader: Callable[[], Any] = None) -> Optional[Any]:
        with self.__mutex:
            v = self.__cache.get(key)
            if v is not None:
                if time.time() > v[0]:
                    del self.__cache[key]
                else:
                    return v[1]
            if loader is not None:
                result = loader()
                if result is not None:
                    self[key] = result
                    return result

            return None

    def pop(self, key: Any) -> Optional[Any]:
        with self.__mutex:
            v = self.__cache.pop(key, None)
            if v is None:
                return None
        return v[1]

    def __len__(self):
        return len(self.__cache)

    def __setitem__(self, key, value):
        with self.__mutex:
            if key not in self.__cache and len(self.__cache) == self.__maxsize:
                # Remove the oldest
                oldest = min(self.__cache.items(), key=lambda v: v[1][1])
                del self.__cache[oldest[0]]
            self.__cache[key] = (time.time() + self.__ttl_seconds, value)
