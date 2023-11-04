import time
from collections import namedtuple
from collections.abc import Callable
from typing import Any

from utils.loghelper import StandardLogger

TimedResult = namedtuple("TimedResult", "result elapsed")


def execute(caller: Callable[[], Any]) -> TimedResult:
    start = time.time_ns()
    result = caller()
    elapsed = time.time_ns() - start
    return TimedResult(result, elapsed)


def to_millis_string(elapsed: int) -> str:
    v = elapsed / 1_000_000
    return f"{v:0.3f} ms"


def to_millis(elapsed: int) -> int:
    return elapsed // 1_000_000


def execute_and_log(logger: StandardLogger,
                    action: str,
                    caller: Callable[[], Any]) -> Any:
    logger.info(f"Executing {action} ...")
    tr = execute(caller)
    logger.info(f"{action}: time={to_millis_string(tr.elapsed)}")
    return tr.result


def timer(logger: StandardLogger, action: str):
    def decorator(func):
        def wrapper(*args, **kwargs):
            return execute_and_log(logger, action, lambda: func(*args, **kwargs))
        return wrapper

    return decorator
