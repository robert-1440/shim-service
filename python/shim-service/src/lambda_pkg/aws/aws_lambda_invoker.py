import json
from typing import Dict, Any, Optional

from botocore.response import StreamingBody

from aws import AwsClient
from bean import BeanName
from lambda_pkg import LambdaInvoker, LambdaFunction


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
        resp = self.client.invoke(
            FunctionName=function.value.name,
            InvocationType="Event",
            Payload=payload
        )
        r = InvokeResponse(resp)
        if r.status_code // 100 != 2:
            raise InvocationException(r)
