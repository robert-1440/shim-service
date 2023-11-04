from typing import Any, Callable


def set_if_not_none(dictionary: dict, key: str, value: Any):
    if value is not None:
        dictionary[key] = value


def get_or_create(dictionary: dict, key: str, loader: Callable):
    v = dictionary.get(key)
    if v is None:
        dictionary[key] = v = loader()
    return v


class ReadOnlyDict(dict):
    def __init__(self, source=None):
        args = []
        if source is not None:
            args.append(source)
        super(ReadOnlyDict, self).__init__(*args)
        self.__source = source

    def __setitem__(self, key, value):
        raise NotImplementedError()

    def __delitem__(self, key):
        raise NotImplementedError()

    def pop(self, __key):
        raise NotImplementedError()

    def popitem(self):
        raise NotImplementedError()

    def clear(self):
        raise NotImplementedError()

    def update(self, __m, **kwargs):
        raise NotImplementedError()

    def __eq__(self, other):
        if isinstance(other, ReadOnlyDict):
            return self.__source == other.__source
        return self.__source == other


EMPTY = ReadOnlyDict()
