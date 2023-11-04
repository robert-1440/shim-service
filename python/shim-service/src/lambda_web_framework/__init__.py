import abc
import atexit
import os
import signal
from typing import Dict, Any

from utils.date_utils import get_system_time_in_seconds
from utils.loghelper import StandardLogger


class WebRequestProcessor(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()


def init_lambda(logger: StandardLogger):
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None:
        logger.info(f"Installing shutdown handler.")
        start_time = get_system_time_in_seconds()
        # Set up for informational purposes, if we are actually in a Lambda
        old_sig = signal.getsignal(signal.SIGTERM)

        def _report():
            elapsed = get_system_time_in_seconds() - start_time
            logger.info(f"Lambda exiting, seconds up: {elapsed}.")

        def _goodbye_handler(signum, frame):
            _report()
            signal.signal(signum, old_sig)
            signal.raise_signal(signum)

        signal.signal(signal.SIGTERM, _goodbye_handler)
        atexit.register(_report)
