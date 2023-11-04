import abc
import base64
import functools
import json
import os.path
import pickle
from typing import Dict, Any

from utils import string_utils, date_utils


class Expirable(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_ttl_seconds(self) -> int:
        raise NotImplementedError()


class _Entry:
    def __init__(self, expire_at: int, payload: str):
        self.expireAt = expire_at
        self.payload = payload


def ensure_parent_exists(file_name: str):
    """
    For the given absolute file name, ensure the parent folder for the file exists.
    :param file_name: the fully-qualified file name.
    """
    parent = os.path.split(file_name)[0]
    if parent is not None and len(parent) > 0 and not os.path.isdir(parent):
        os.makedirs(parent)


class PersistedCache:
    def __init__(self, file_name: str):
        self.__file_name = file_name
        self.__cache: Dict[str, _Entry] = {}
        if os.path.isfile(file_name):
            with open(file_name) as f:
                cache = json.load(f)
            for key, value in cache.items():
                self.__cache[key] = _Entry(value['expireAt'], value['payload'])

    def __store(self):
        ensure_parent_exists(self.__file_name)
        with open(self.__file_name, "w") as f:
            cache = {}
            for key, value in self.__cache.items():
                cache[key] = value.__dict__
            json.dump(cache, f, indent=True)

    def clear(self):
        if len(self.__cache) > 0:
            self.__cache.clear()
            self.__store()

    def cached(self, ttl_seconds: int):
        def decorator(wrapped_function):
            @functools.wraps(wrapped_function)
            def _inner_wrapper(key: str):
                entry: _Entry = self.__cache.get(key)
                if entry is None or date_utils.get_system_time_in_millis() > entry.expireAt:
                    obj = wrapped_function(key)
                    if obj is None:
                        return None

                    if isinstance(obj, Expirable):
                        use_seconds = obj.get_ttl_seconds()
                    else:
                        use_seconds = ttl_seconds

                    expire_at = date_utils.get_system_time_in_millis() + (use_seconds * 1000)
                    pickled = pickle.dumps(obj)
                    entry = _Entry(expire_at, string_utils.encode_to_base64string(pickled))
                    self.__cache[key] = entry
                    self.__store()
                    return obj
                else:
                    return pickle.loads(base64.decodebytes(entry.payload.encode('utf-8')))

            return _inner_wrapper

        return decorator

    def cached_enclosed(self, ttl_seconds: int):
        def decorator(wrapped_function):
            @functools.wraps(wrapped_function)
            def _inner_wrapper(thing: Any, key: str):
                entry: _Entry = self.__cache.get(key)
                if entry is None or date_utils.get_system_time_in_millis() > entry.expireAt:
                    obj = wrapped_function(thing, key)
                    if obj is None:
                        return None

                    if isinstance(obj, Expirable):
                        use_seconds = obj.get_ttl_seconds()
                    else:
                        use_seconds = ttl_seconds

                    expire_at = date_utils.get_system_time_in_millis() + (use_seconds * 1000)
                    pickled = pickle.dumps(obj)
                    entry = _Entry(expire_at, string_utils.encode_to_base64string(pickled))
                    self.__cache[key] = entry
                    self.__store()
                    return obj
                else:
                    return pickle.loads(base64.decodebytes(entry.payload.encode('utf-8')))

            return _inner_wrapper

        return decorator
