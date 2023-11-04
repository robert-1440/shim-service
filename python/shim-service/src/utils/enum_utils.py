from enum import Enum
from threading import RLock
from typing import Type, Dict, Any, Callable


def build_value_table(enum_type: Type[Enum],
                      key_getter: Callable[[Any], Any]) -> Dict[Any, Enum]:
    """
    Used to build a reverse-lookup table for an enum type.

    :param enum_type: the enum type
    :param key_getter: optional mapper to get the value to use for the key.
    :return: a dictionary with values as the key and enums as the value
    """
    record = {}
    if key_getter is None:
        for v in enum_type:
            record[v.value] = v
    else:
        for v in enum_type:
            key = key_getter(v.value)
            record[key] = v

    return record


class ReverseLookupEnum(Enum):
    __reverse_table__ = None

    __mutex__ = RLock()

    @classmethod
    def _value_of(cls, value: Any, thing: str) -> Any:
        if cls.__reverse_table__ is None:
            with cls.__mutex__:
                if cls.__reverse_table__ is None:
                    cls.__reverse_table__ = build_value_table(cls, cls.value_for_enum)
            cls.__mutex__ = None

        v = cls.__reverse_table__.get(value)
        if v is not None:
            return v
        raise ValueError(f"Invalid {thing}: '{value}'.")

    @classmethod
    def value_for_enum(cls, v: Any) -> Any:
        return v
