import abc
from enum import Enum
from typing import Dict, Any, Optional

from bean import BeanName
from lambda_pkg.functions import LambdaFunction
from utils import date_utils
from utils.date_utils import EpochSeconds


class ScheduleTargetType(Enum):
    AT = 0
    RATE = 1


class ScheduleTarget(metaclass=abc.ABCMeta):
    def __init__(self,
                 value: Any):
        self.value = value

    @classmethod
    @abc.abstractmethod
    def target_type(cls) -> ScheduleTargetType:
        raise NotImplementedError()


class ScheduleTargetTime(ScheduleTarget):
    def __init__(self, at_time: EpochSeconds):
        super(ScheduleTargetTime, self).__init__(at_time)

    @classmethod
    def target_type(cls) -> ScheduleTargetType:
        return ScheduleTargetType.AT


class ScheduleTargetRate(ScheduleTarget):
    def __init__(self, minutes: int):
        super(ScheduleTargetRate, self).__init__(minutes)

    @classmethod
    def target_type(cls) -> ScheduleTargetType:
        return ScheduleTargetType.RATE


def minutes_in_future_target(minutes: int) -> ScheduleTarget:
    assert minutes > 0
    return ScheduleTargetTime(date_utils.get_epoch_seconds_in_future(minutes * 60, round_to_minute=True))


class Scheduler(metaclass=abc.ABCMeta):

    def schedule_live_agent_poller(self, delay_seconds: Optional[int] = None):
        self.schedule_lambda(LambdaFunction.LiveAgentPoller, {}, delay_seconds)

    @abc.abstractmethod
    def schedule_lambda(self,
                        function: LambdaFunction,
                        parameters: Dict[str, Any],
                        seconds_in_future: int = None,
                        bean_name: BeanName = None,
                        ):
        raise NotImplementedError()

    @abc.abstractmethod
    def process_sqs_event(self, record: dict):
        raise NotImplementedError()
