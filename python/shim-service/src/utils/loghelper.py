import logging
import os.path
import sys
import threading
from logging import Logger, Formatter, StreamHandler
from types import ModuleType
from typing import Union, Dict, Any, Callable, Optional

from bean import BeanName, inject
from notification import Notifier
from utils import exception_utils
from utils.exception_utils import never_raise

logging.basicConfig(level=logging.INFO,
                    format='%(asctime)s.%(msecs)03d [%(process)6d] %(levelname)-7s:  %(name)-40s  %(message)s',
                    datefmt='%m/%d/%Y %H:%M:%S')

formatter = Formatter('%(asctime)s.%(msecs)03d [%(process)6d] %(levelname)-7s:  %(name)-40s  %(message)s',
                      datefmt='%m/%d/%Y %H:%M:%S')

handler = StreamHandler()
handler.setLevel(logging.INFO)
handler.setFormatter(formatter)

LoggingHook = Callable[[str], None]

INFO_LOGGING_HOOK: Optional[LoggingHook] = None

__thread_local = threading.local()


def set_logging_info(data: Dict[str, Any]):
    __thread_local.data = data


def clear_logging_info():
    if hasattr(__thread_local, 'data'):
        delattr(__thread_local, 'data')


def _add_logging_info(msg: str) -> str:
    if hasattr(__thread_local, 'data'):
        data: dict = __thread_local.data
        prefix = ""
        for key, value in data.items():
            if len(prefix) > 0:
                prefix += ' '
            prefix += f'[{key}={value}]'
        return f"<<{prefix}>> {msg}"
    return msg


@inject(bean_instances=BeanName.ERROR_NOTIFIER)
def error_notify(subject: str, message: str, notifier: Notifier):
    try:
        notifier.notify(subject, message)
    except BaseException as ex:
        exception_utils.print_exception(ex)


class StandardLogger:
    def __init__(self, logger: Logger):
        self.__logger = logger

    @never_raise(notifier=error_notify)
    def debug(
            self,
            msg: str,
            *args) -> None:
        self.__logger.debug(_add_logging_info(msg), *args)

    @never_raise(notifier=error_notify)
    def info(
            self,
            msg: str,
            *args) -> None:
        message = _add_logging_info(msg)
        if INFO_LOGGING_HOOK is not None:
            INFO_LOGGING_HOOK(message)

        self.__logger.info(message, *args)

    @never_raise(notifier=error_notify)
    def warning(
            self,
            msg: str,
            *args
    ) -> None:
        self.__logger.warning(_add_logging_info(msg), *args)

    @never_raise(notifier=error_notify)
    def error(
            self,
            msg: str,
            *args) -> None:
        self.__logger.error(_add_logging_info(msg), *args)

    @never_raise(notifier=error_notify)
    def severe(self,
               message: str,
               ex: BaseException = None) -> str:
        output = message
        if ex is not None:
            ret_message = exception_utils.get_exception_message(ex)
            output += f"\n{exception_utils.dump_ex(ex)}"
        else:
            output = ret_message = message
        self.error(output)
        subject = "ShimService Error"
        lf = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        if lf is not None:
            subject += f" from Lambda Function {lf}"

        error_notify(subject, output)
        return ret_message


def __extract_name(name: Union[ModuleType, str]) -> str:
    if isinstance(name, ModuleType):
        fn = name.__file__
        if not os.path.isabs(fn):
            fn = os.path.realpath(fn)
        name = name.__name__
        index = fn.find("/src/")
        if index > 0:
            s = fn[index + 5::]
            index = s.rfind(".py")
            if index > 0:
                name = s[0:index:].replace("/", ".")
    return name


def get_logger(name: Union[ModuleType, str]) -> StandardLogger:
    name = __extract_name(name)
    logger = logging.Logger(name, level=logging.INFO)
    logger.addHandler(handler)
    return StandardLogger(logger)


def get_module_logger(name: str) -> StandardLogger:
    return get_logger(sys.modules[name])


def execute_with_logging_info(data: Dict[str, Any], caller: Callable) -> Any:
    set_logging_info(data)
    try:
        return caller()
    finally:
        clear_logging_info()
