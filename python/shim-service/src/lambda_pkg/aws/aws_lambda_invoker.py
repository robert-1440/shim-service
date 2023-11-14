import json
from typing import Dict, Any, Optional

from botocore.response import StreamingBody

from aws import AwsClient
from bean import BeanName
from lambda_pkg.functions import LambdaFunction
from lambda_pkg.functions import LambdaInvoker
from utils import loghelper

logger = loghelper.get_logger(__name__)

class InvokeResponse:
    def __init__(self, node: Dict[str, Any]):
        self.status_code: int = node['StatusCode']
        self.function_error: Optional[str] = node.get('FunctionError')
        self.log_result: Optional[str] = node.get('LogResult')
        self.payload: Optional[StreamingBody] = node.get('Payload')
        self.executed_version: str = node.get('ExecutedVersion')

    def to_json(self) -> str:
        record = dict(self.__dict__)
        del record['payload']
        return json.dumps(record, indent=True)

    def __str__(self):
        return self.to_json()

    def __repr__(self):
        return self.__str__()


class InvocationException(Exception):
    def __init__(self, response: InvokeResponse):
        super(InvocationException, self).__init__(f"{response.status_code}: {response.function_error}")
        self.response = response


class AwsLambdaInvoker(LambdaInvoker):

    def __init__(self, client: AwsClient):
        self.client = client

    def invoke_function(self,
                        function: LambdaFunction,
                        parameters: Dict[str, Any],
                        bean_name: BeanName = None):
        if bean_name is None:
            bean_name = function.value.default_bean_name
        record = {
            'bean': bean_name.name,
            'parameters': parameters
        }

        payload = json.dumps(record).encode('utf-8')
        name = function.value.effective_name
        logger.info(f"Attempting to invoke lambda function {name}.")
        resp = self.client.invoke(
            FunctionName=name,
            InvocationType="Event",
            Payload=payload
        )
        r = InvokeResponse(resp)
        if r.status_code // 100 != 2:
            raise InvocationException(r)
