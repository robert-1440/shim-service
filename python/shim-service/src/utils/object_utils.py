import inspect
from typing import Any


def coalesce_callable(*args):
    """
    Finds the first non-None value and returns it.  The last argument should be a "callable".

    :param args: the arguments
    :return: the first non None value, or what the callable reutrns.
    """

    size = len(args)
    for i in range(size - 1):
        v = args[i]
        if v is not None:
            return v
    return args[size - 1]()


def get_class_name(obj: Any) -> str:
    if obj is None:
        return "NoneType"
    t = type(obj)
    assert inspect.isclass(t)

    return obj.__class__.__name__
