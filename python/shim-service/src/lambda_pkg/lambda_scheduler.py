import json
import os
from typing import Dict, Any

import requests
from botocore.auth import SigV4Auth
from botocore.awsrequest import AWSRequest
from botocore.credentials import Credentials

from lambda_web_framework import InvocableBeanRequestHandler
from utils import loghelper
from utils.supplier import MemoizedSupplier

logger = loghelper.get_logger(__name__)

hit_counter = 0

region = os.environ.get('AWS_REGION')


def _load_credentials():
    return Credentials(
        os.environ['AWS_ACCESS_KEY_ID'],
        os.environ['AWS_SECRET_ACCESS_KEY'],
        os.environ['AWS_SESSION_TOKEN']
    )


credentials_supplier = MemoizedSupplier(_load_credentials)


def _sign_aws_lambda_request(url: str, payload: str, invocation_type: str = 'Event'):
    sigv4_auth = SigV4Auth(credentials_supplier.get(), "lambda", os.environ['AWS_REGION'])

    aws_request = AWSRequest(
        method="POST",
        url=url,
        data=payload,
        headers={
            'Content-Type': 'application/json',
            'X-Amz-Invocation-Type': invocation_type,
        }
    )

    sigv4_auth.add_auth(aws_request)

    return aws_request


def invoke(function_name: str, parameters: Dict[str, Any]):
    body = json.dumps(parameters)
    endpoint = f'https://lambda.{region}.amazonaws.com/2015-03-31/functions/{function_name}/invocations'
    signed_request = _sign_aws_lambda_request(endpoint, body)
    global hit_counter
    hit_counter += 1

    logger.info(f"Attempting to invoke lambda function {function_name}, hits={hit_counter} ...")
    response = requests.post(
        endpoint,
        headers=signed_request.headers,
        data=signed_request.body,
    )
    code = response.status_code
    if code // 100 != 2:
        logger.severe(f"Failed to invoke lambda function {function_name}, code={code}, response={response.text}")


class LambdaSchedulerProcessor(InvocableBeanRequestHandler):

    def invoke(self, parameters: Dict[str, Any]):
        target_function = parameters.pop('targetFunction')
        invoke(target_function, parameters)
