import time
from threading import RLock
from typing import Any, Dict, Callable, Optional


class _CacheEntry:
    def __init__(self, value: Any, expire_at: float):
        self.value = value
        self.expire_at = expire_at


class ConcurrentTtlCache:
    def __init__(self, maxsize: int, ttl: float,
                 loader: Callable[[Any], Any] = None):
        """
        A cache that does its best to allow concurrent access to different keys,

        :param maxsize: the maximum size of the cache.
        :param ttl:  the ttl, in seconds, for each entry.
        :param loader: Optional loader to use when keys are not found.
        """
        assert maxsize > 1
        self.__maxsize = maxsize
        self.__shard_size = max(0, maxsize // 4) + 1
        assert ttl > 0
        self.__ttl_seconds = ttl
        self.__cache: Dict[Any, _CacheEntry] = {}
        self.__mutexes: Dict[int, RLock] = {}
        self.__mutex = RLock()
        self.__loader = loader

    def __get_shard_mutex(self, key: Any) -> RLock:
        h = hash(key)
        if h < 0:
            h = -h
        index = h % self.__shard_size
        m = self.__mutexes.get(index)
        if m is None:
            with self.__mutex:
                m = self.__mutexes.get(index)
                if m is None:
                    self.__mutexes[index] = m = RLock()
        return m

    def find(self, key: Any) -> Optional[Any]:
        with self.__get_shard_mutex(key):
            current = self.__cache.get(key)
            if current is not None:
                if current.expire_at > time.time():
                    return current.value
                self.__cache.pop(key, None)
            return None

    def __load(self, key: Any, loader: Callable[[], Any]):
        if loader is not None:
            return loader()
        if self.__loader is not None:
            return self.__loader(key)
        return None

    def __get(self, key: Any, loader: Callable[[], Any] = None) -> Optional[Any]:
        with self.__get_shard_mutex(key):
            # We are taking advantage of the GIL here
            # If an attempt to call this with the same key is done, we'll block on the shard index
            current = self.__cache.get(key)
            if current is not None and current.expire_at > time.time():
                return current.value
            value = self.__load(key, loader)
            if value is not None:
                self.__set(key, value, lock_shard=False)
                return value
        return None

    def get(self, key: Any, loader: Callable[[], Any] = None) -> Optional[Any]:
        """
        Used to get a key, and, optionally attempt to load the value for the key.

        :param key: the key.
        :param loader: optional loader to call if the key does not exist. If None, and the cache
        was constructed with a loader, that loader will be used.  Use find() if you do not want to load.
        :return: the current value, None if not in the cache, or the loader returned None
        """
        return self.__get(key, loader)

    def invalidate(self, key: Any, action: Callable[[Any], None] = None) -> Optional[Any]:
        """
        Removes the given key, and calls the optional action if the key was found.

        :param key: the key.
        :param action: the action to call with the current value if the key was found.
        :return: the current value, None if the key did not exist.
        """
        with self.__get_shard_mutex(key):
            # GIL allows this, otherwise we'd have to lock the main mutex
            entry = self.__cache.pop(key, None)
            if entry is None:
                return None
            if action is not None:
                action(entry.value)
            return entry.value

    def clear(self):
        self.__cache.clear()

    def __len__(self):
        return len(self.__cache)

    def __set(self, key, value, lock_shard: bool = True):
        if lock_shard:
            shard_mutex = self.__get_shard_mutex(key)
            shard_mutex.acquire()
        else:
            shard_mutex = None

        try:
            with self.__mutex:
                if key not in self.__cache and len(self.__cache) == self.__maxsize:
                    # Remove the oldest
                    oldest = min(self.__cache.items(), key=lambda v: v[1].expire_at)
                    del self.__cache[oldest[0]]
                entry = _CacheEntry(value, time.time() + self.__ttl_seconds)
                self.__cache[key] = entry
        finally:
            if shard_mutex is not None:
                shard_mutex.release()

    def __setitem__(self, key, value):
        self.__set(key, value)
