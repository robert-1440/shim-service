import abc
from typing import Iterable

from pending_event import PendingEventType, PendingEvent
from repos import QueryResult


class PendingEventsRepo(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def query_events(self, event_type: PendingEventType, limit: int) -> QueryResult:
        raise NotImplementedError()

    @abc.abstractmethod
    def update_action_time(self, event: PendingEvent, seconds_in_future: int) -> bool:
        raise NotImplementedError()

    @abc.abstractmethod
    def update_action_times(self, events: Iterable[PendingEvent], seconds_in_future: int):
        raise NotImplementedError()

    @abc.abstractmethod
    def delete_event(self, event: PendingEvent) -> bool:
        raise NotImplementedError()
