import abc
import os
from typing import Dict, Any, Optional

import boto3
import botocore

from utils.loghelper import StandardLogger


class RequestHandler(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()


class WebRequestProcessor(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()


def init_lambda(logger: StandardLogger):
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None:
        logger.info(f"boto3 version is {boto3.__version__}; botocore={botocore.__version__}")
