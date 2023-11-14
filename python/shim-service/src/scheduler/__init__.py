import abc
from enum import Enum
from typing import Dict, Any

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
    @abc.abstractmethod
    def delete_schedule(self, group_name: str, name: str) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def schedule_lambda(self,
                        schedule_name: str,
                        schedule_target: ScheduleTarget,
                        function: LambdaFunction,
                        parameters: Dict[str, Any]) -> bool:
        raise NotImplementedError()

    def schedule_lambda_minutes(self, schedule_name: str,
                                minutes_in_future: int,
                                function: LambdaFunction,
                                event: Dict[str, Any]) -> bool:
        """
        Used to schedule a lamda function invocation.

        :param schedule_name: the name to use for the schedule.
        :param minutes_in_future: the minutes in the future the invocation should take place.
        :param function: the lambda function to invoke.
        :param event: the event to include.
        :return: True if the schedule was created, False if it existed already.
        """
        return self.schedule_lambda(
            schedule_name,
            minutes_in_future_target(minutes_in_future),
            function,
            event
        )
