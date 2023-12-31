import json
import os
from datetime import datetime
from typing import Any, Dict

from aws import is_not_found_exception, is_conflict_exception, AwsClient
from lambda_pkg.functions import LambdaFunction
from lambda_pkg.params import LambdaFunctionParameters
from scheduler import Scheduler, ScheduleTarget, ScheduleTargetType
from utils import loghelper
from utils.dict_utils import set_if_not_none

_FLEX_WINDOW = {"Mode": "OFF"}

logger = loghelper.get_logger(__name__)


def _format_at(dt: datetime) -> str:
    return f"at({dt.year:04d}-{dt.month:02d}-{dt.day:02d}T{dt.hour:02d}:{dt.minute:02d})"


def _format_rate(minutes: int) -> str:
    unit = "minute"
    if minutes > 1:
        unit += "s"
    return f"rate({minutes} {unit})"


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
    def __init__(self, client: AwsClient, lambda_client: AwsClient):
        self.client = client
        self.lambda_client = lambda_client

    @staticmethod
    def _build_params(function_arn: str,
                      role_arn: str,
                      group_name: str,
                      name: str,
                      payload: Dict[str, Any],
                      schedule_target: ScheduleTarget) -> Dict[str, Any]:

        target = {
            'RoleArn': role_arn,
            'Arn': function_arn,
            'Input': json.dumps(payload)
        }

        params = {
            'Name': name,
            'GroupName': group_name,
            'Target': target,
            'FlexibleTimeWindow': _FLEX_WINDOW
        }
        _fill_schedule_params(schedule_target, params)
        return params

    def __create_schedule(self,
                          group_name: str,
                          name: str,
                          function_arn: str,
                          role_arn: str,
                          payload: Dict[str, Any],
                          target: ScheduleTarget):
        params = self._build_params(function_arn, role_arn, group_name, name, payload, target)
        try:
            logger.info(f"Attempting to create schedule:\n{json.dumps(params, indent=True)})")
            self.client.create_schedule(**params)
        except Exception as ex:
            if is_conflict_exception(ex):
                return False
            raise ex
        return True

    def get_arn(self, function: LambdaFunction):
        our_arn = os.environ.get('THIS_FUNCTION_ARN')
        if our_arn is not None:
            values = our_arn.split(':')
            values[6] = function.value.effective_name
            return ':'.join(values)

        resp = self.lambda_client.get_function(FunctionName=function.value.effective_name)
        return resp['Configuration']['FunctionArn']

    def schedule_lambda(self,
                        schedule_name: str,
                        schedule_target: ScheduleTarget,
                        function: LambdaFunction,
                        parameters: Dict[str, Any]) -> bool:
        arn = self.get_arn(function)
        func_params: LambdaFunctionParameters = function.value

        event = {
            'bean': func_params.default_bean_name.name,
            'parameters': parameters
        }
        return self.__create_schedule(
            func_params.scheduler_group,
            schedule_name,
            arn,
            func_params.scheduler_role_arn,
            event,
            schedule_target
        )

    def delete_schedule(self, group_name: str, name: str):
        try:
            self.client.delete_schedule(Name=name, GroupName=group_name)
            return True
        except Exception as ex:
            if is_not_found_exception(ex):
                return False
            raise ex
