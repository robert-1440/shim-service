import json
from typing import Any, Dict

from aws import AwsClient
from bean import BeanName
from lambda_pkg.functions import LambdaFunction
from lambda_pkg.params import LambdaFunctionParameters
from scheduler import Scheduler
from utils import loghelper
from utils.exception_utils import dump_ex

logger = loghelper.get_logger(__name__)


class AwsScheduler(Scheduler):
    def __init__(self, sqs_client: AwsClient):
        self.sqs_client = sqs_client

    def schedule_lambda(self,
                        function: LambdaFunction,
                        parameters: Dict[str, Any],
                        seconds_in_future: int = None,
                        bean_name: BeanName = None,
                        ):
        if bean_name is None:
            bean_name = function.value.default_bean_name
        record = {
            'bean': bean_name.name,
            'parameters': parameters
        }

        payload = json.dumps(record)

        function_parameters: LambdaFunctionParameters = function.value
        params = {
            'QueueUrl': function_parameters.queue_url,
            'MessageBody': payload
        }
        if seconds_in_future is not None and seconds_in_future > 0:
            params['DelaySeconds'] = seconds_in_future

        logger.info(f"Sending queue message:\n{json.dumps(params, indent=True)})")
        self.sqs_client.send_message(**params)

    def process_sqs_event(self, record: dict):
        receipt_handle = record.get('receiptHandle')
        if receipt_handle is None:
            return
        arn = record.get('eventSourceARN')
        if arn is None:
            return
        values = arn.split(":")
        name = values[len(values) - 1]

        resp = self.sqs_client.get_queue_url(QueueName=name)
        try:
            self.sqs_client.delete_message(QueueUrl=resp['QueueUrl'], ReceiptHandle=receipt_handle)
        except BaseException as ex:
            logger.error(f"Failed to delete queue message: {dump_ex(ex)}")
