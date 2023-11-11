import json
from datetime import datetime
from typing import Any, Dict

from aws import AwsClient
from bean import BeanName
from lambda_pkg import LambdaFunction
from scheduler import Scheduler, ScheduleTarget, ScheduleTargetType
from utils import loghelper
from utils.dict_utils import set_if_not_none
from utils.exception_utils import dump_ex

_FLEX_WINDOW = {"Mode": "OFF"}

logger = loghelper.get_logger(__name__)


def _format_at(dt: datetime) -> str:
    return f"at({dt.year:04d}-{dt.month:02d}-{dt.day:02d}T{dt.hour:02d}:{dt.minute:02d})"


def _format_rate(minutes: int) -> str:
    unit = "minute"
    if minutes > 1:
        unit += "s"
    return f"rate({minutes} {unit})"


def get_role(function: LambdaFunction):
    name = function.value


def _fill_schedule_params(target: ScheduleTarget, record: Dict[str, Any]):
    t = target.target_type()
    after_completion = None

    if t == ScheduleTargetType.AT:
        start_dt = datetime.fromtimestamp(target.value)
        schedule_exp = _format_at(start_dt)
        after_completion = "DELETE"
    elif t == ScheduleTargetType.RATE:
        schedule_exp = _format_rate(target.value)
    else:
        raise NotImplementedError(f"No support for {t}")

    set_if_not_none(record, "ActionAfterCompletion", after_completion)
    record['ScheduleExpression'] = schedule_exp


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

        params = {
            'QueueUrl': function.value.queue_url,
            'MessageBody': payload
        }
        if seconds_in_future is not None and seconds_in_future > 0:
            params['DelaySeconds'] = seconds_in_future
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
