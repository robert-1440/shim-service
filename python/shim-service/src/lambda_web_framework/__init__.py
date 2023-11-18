import abc
import os
from typing import Dict, Any, Optional

import boto3
import botocore

from bean import InvocableBean
from lambda_web_framework.request import LambdaHttpRequest, LambdaHttpResponse
from lambda_web_framework.web_exceptions import LambdaHttpException
from utils.loghelper import StandardLogger

SUCCESS_RESPONSE = {"statusCode": 200, "body": "OK"}

our_logger: Optional[StandardLogger] = None


class RequestHandler(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def handle(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        raise NotImplementedError()


class InvocableBeanRequestHandler(RequestHandler, InvocableBean, metaclass=abc.ABCMeta):
    def handle(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        name = event.get('bean')
        if name is None:
            return None
        if name == self.bean_name.name:
            return self.invoke(event.get('parameters')) or SUCCESS_RESPONSE
        return None


class WebRequestProcessor(RequestHandler, metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        raise NotImplementedError()

    def handle(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        if not LambdaHttpRequest.is_web_event(event):
            return None
        try:
            r = self.process(event)
            if isinstance(r, LambdaHttpResponse):
                return r.to_dict()
            return r
        except LambdaHttpException as ex:
            our_logger.error(f"Error: {ex}")
            return ex.to_response()


def init_lambda(logger: StandardLogger):
    global our_logger
    our_logger = logger
    if os.environ.get('AWS_LAMBDA_FUNCTION_NAME') is not None:
        logger.info(f"boto3 version is {boto3.__version__}; botocore={botocore.__version__}")
