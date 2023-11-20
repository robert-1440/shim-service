import abc
from typing import Any

from repos import QueryResult
from tenant import PendingTenantEvent, PendingTenantEventType


class PendingTenantEventRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def update_or_create(self, event: PendingTenantEvent):
        raise NotImplementedError()

    @abc.abstractmethod
    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_event(self, event: PendingTenantEvent) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def query_events(self, event_type: PendingTenantEventType, limit: int, next_token: Any) -> QueryResult:
        raise NotImplementedError()

