import json
import os
import logging
from logging import StreamHandler
from threading import local
from typing import Callable, Optional

LoggingHook = Callable[[str], None]

_logging_hook: Optional[LoggingHook] = None


class JsonFormatter(logging.Formatter):

    def __init__(self, thread_local: local):
        super().__init__()
        self.thread_local = thread_local
        self._ignore_keys = {'msg', 'args', 'process',
                             'processName', 'thread', 'relativeCreated', 'lineno',
                             'levelno', 'msecs', 'funcName', 'pathname', 'filename',
                             'module', 'exc_text', 'exc_info', 'stack_info', 'created',
                             'levelname'
                             }

    def format(self, record: logging.LogRecord) -> str:
        log_record = record.__dict__.copy()
        log_record['message'] = record.getMessage()
        log_record['level'] = record.levelname

        for key in self._ignore_keys:
            log_record.pop(key, None)

        log_record['timestamp'] = int(record.created * 1000)

        if hasattr(self.thread_local, 'data'):
            log_record.update(self.thread_local.data)

        output = json.dumps(log_record)

        if _logging_hook is not None:
            _logging_hook(output)

        return output


def setup(handler: StreamHandler, thread_local: local):
    handler.setFormatter(JsonFormatter(thread_local))


def set_logging_hook(hook: Optional[LoggingHook]):
    global _logging_hook
    _logging_hook = hook
