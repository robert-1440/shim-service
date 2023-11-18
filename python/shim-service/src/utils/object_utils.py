import inspect
from typing import Any


def get_class_name(obj: Any) -> str:
    if obj is None:
        return "NoneType"
    t = type(obj)
    assert inspect.isclass(t)

    return obj.__class__.__name__
