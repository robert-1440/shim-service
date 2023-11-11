import json
import os
from typing import Dict, Any, Optional

from botocore.response import StreamingBody

from aws import AwsClient
from bean import BeanName, BeanSupplier
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

    def __init__(self, client: AwsClient, sqs_client_supplier: BeanSupplier[AwsClient]):
        self.client = client
        self.sqs_client_supplier = sqs_client_supplier
        self.our_function_name = os.environ.get('AWS_LAMBDA_FUNCTION_NAME')
        self.__queue_url: Optional[str] = None

    def __sqs_initialized(self):
        name = f"SQS_{self.our_function_name.upper()}_QUEUE_URL"
        self.__queue_url = os.environ[name]

    def __submit_to_queue(self, message: str, delay_seconds: Optional[int]):
        client = self.sqs_client_supplier.get(self.__sqs_initialized)
        params = {
            'QueueUrl': self.__queue_url,
            'MessageBody': message
        }
        if delay_seconds is not None:
            params['DelaySeconds'] = delay_seconds
        client.send_message(**params)

    def invoke_function(self,
                        function: LambdaFunction,
                        parameters: Dict[str, Any],
                        bean_name: BeanName = None,
                        delay_seconds: int = None):
        if bean_name is None:
            bean_name = function.value.default_bean_name
        record = {
            'bean': bean_name.name,
            'parameters': parameters
        }

        payload = json.dumps(record)
        if self.our_function_name is not None and self.our_function_name == function.value.name:
            self.__submit_to_queue(payload, delay_seconds)
        else:
            resp = self.client.invoke(
                FunctionName=function.value.name,
                InvocationType="Event",
                Payload=payload.encode('utf-8')
            )
            r = InvokeResponse(resp)
            if r.status_code // 100 != 2:
                raise InvocationException(r)
