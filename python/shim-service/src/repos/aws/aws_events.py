import abc
from typing import List, Optional, Collection

from aws.dynamodb import DynamoDb, TransactionRequest
from events import Event
from repos import QueryResult
from repos.aws import SHIM_SERVICE_EVENT_TABLE
from repos.aws.abstract_repo import AbstractAwsRepo
from repos.events import EventsRepo


class EventListener(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def event_received(self, event: Event, request_list: List[TransactionRequest]):
        raise NotImplementedError()


class AwsEventsRepo(AbstractAwsRepo, EventsRepo):
    __table_name__ = SHIM_SERVICE_EVENT_TABLE
    __hash_key__ = 'tenantId'
    __range_key__ = 'seqNo'

    __initializer__ = Event.from_record

    def __init__(self, ddb: DynamoDb, listeners: Optional[Collection[EventListener]]):
        super(AwsEventsRepo, self).__init__(ddb)
        self.listeners = listeners

    def query_events(self, tenant_id: int,
                     limit: int = 100,
                     last_seq_no: int = None,
                     last_evaluated_key=None) -> QueryResult:
        return self.query(
            tenant_id,
            start_after=last_seq_no,
            limit=limit,
            last_evaluated_key=last_evaluated_key
        )

    def examine_event(self, event: Event) -> Optional[List[TransactionRequest]]:
        if self.listeners is None:
            return None

        request_list = []
        for listener in self.listeners:
            listener.event_received(event, request_list)
        return request_list if len(request_list) > 0 else None
