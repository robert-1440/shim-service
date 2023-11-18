import functools
import sys
import traceback
from io import StringIO
from traceback import print_exc
from typing import Any, Callable


def get_exception_message(ex):
    if hasattr(ex, "message"):
        return ex.message
    else:
        return f"{ex}"


def dump_ex(ex: Any = None) -> str:
    """
    Used to dump the current exception.

    :return: the stack trace string
    """
    io = StringIO()

    if ex is not None:
        print(f"<<< Exception: {get_exception_message(ex)} >>>\n", file=io)
    print_exc(None, io)
    return io.getvalue()


def execute_no_raise(caller: Callable) -> Any:
    try:
        return caller()
    except BaseException:
        print_exc()
    return None


def never_raise(notifier: Callable[[str, str], None] = None):
    """
    Use this to decorate functions that should never let an exception be raised (for logging, etc).
    Use with caution.
    """

    def decorator(wrapped_function):
        @functools.wraps(wrapped_function)
        def _inner_wrapper(*args, **kwargs):
            try:
                return wrapped_function(*args, **kwargs)
            except BaseException as ex:
                message = dump_ex(ex)
                print(message, file=sys.stderr)
                if notifier is not None:
                    execute_no_raise(lambda: notifier("Unexpected Exception", message))

            return None

        return _inner_wrapper

    return decorator


def print_exception(ex: BaseException):
    try:
        if sys.version_info >= (3, 10):
            traceback.print_exception(ex, file=sys.stderr)
        else:
            traceback.print_exception(type(ex), ex, ex.__traceback__, file=sys.stderr)
    except BaseException:
        print_exc()
