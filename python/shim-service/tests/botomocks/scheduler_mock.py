import re
from datetime import datetime
from typing import Optional, Dict

from botomocks import BaseMockClient, assert_empty, raise_conflict_exception, KeyId, raise_not_found, lambda_mock
from lambda_web_framework.request import get_required_parameter, get_parameter

_NAME_REGEX = re.compile(r"^[0-9a-zA-Z-_.]+$")
_AT_REGEX = re.compile(r'at\((\d{4}-\d{2}-\d{2}T\d{2}:\d{2})\)')


class Target:
    def __init__(self, node: dict):
        node = dict(node)
        self.role_arn = get_required_parameter(node, "RoleArn", str, remove=True)
        self.arn = get_required_parameter(node, "Arn", str, remove=True)
        self.input = get_required_parameter(node, "Input", str, remove=True)
        assert_empty(node)


class Schedule:
    name: str
    group_name: Optional[str]
    schedule_expression: str
    start_date: Optional[datetime]
    target: Target
    flexible_time_window: Dict[str, str]

    def __init__(self, node: dict):
        node = dict(node)
        self.name = get_required_parameter(node, "Name", str, remove=True)
        self.group_name = get_parameter(node, "GroupName", str, remove=True)
        self.schedule_expression = get_required_parameter(node, "ScheduleExpression", str, remove=True)
        self.target = Target(get_required_parameter(node, "Target", dict, remove=True))
        self.flexible_time_window = get_required_parameter(node, "FlexibleTimeWindow", dict, remove=True)
        self.after_action = get_parameter(node, "ActionAfterCompletion", str, remove=True)

        assert_empty(node)
        assert 0 < len(self.name) < 65
        assert re.match(_NAME_REGEX, self.name), f"Invalid schedule name: {self.name}"
        assert self.flexible_time_window == {"Mode": "OFF"}
        if self.after_action is not None:
            assert self.after_action == "DELETE"

        match = re.search(_AT_REGEX, self.schedule_expression)
        if match is None:
            raise NotImplementedError(f"Unsupported schedule expression: {self.schedule_expression}")


class MockSchedulerClient(BaseMockClient):

    def __init__(self):
        super().__init__()
        self.schedules: Dict[KeyId, Schedule] = {}
        self.__raise_exists_on_next_create = False

    def set_raise_exists_on_next_create(self):
        self.__raise_exists_on_next_create = True

    def find_schedule_by_session(self, group_name: str, name: str):
        key_id = KeyId(group_name, name)
        return self.schedules.get(key_id)

    def create_schedule(self, **kwargs):
        schedule = Schedule(kwargs)
        key_id = KeyId(schedule.group_name or "default", schedule.name)
        if key_id in self.schedules or self.__raise_exists_on_next_create:
            self.__raise_exists_on_next_create = False
            raise_conflict_exception("CreateSchedule",
                                     f"Schedule with name {schedule.name} already exists.")
        self.schedules[key_id] = schedule

    def delete_schedule(self, **kwargs):
        group_name = kwargs.pop("GroupName", "default")
        name = kwargs.pop("Name")
        assert_empty(kwargs)
        key_id = KeyId(group_name, name)
        removed = self.schedules.pop(key_id, None)
        if removed is None:
            raise_not_found("DeleteSchedule", "Schedule not found")

    def invoke_schedules(self) -> int:
        for schedule in self.schedules.values():
            target = schedule.target
            lambda_mock.invoke_by_arn(target.arn, target.input)
        count = len(self.schedules)
        self.schedules.clear()
        return count

    def create_paginator(self, operation_name: str):
        pass
