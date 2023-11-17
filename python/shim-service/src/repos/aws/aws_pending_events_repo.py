from copy import copy
from typing import Iterable, Any

from aws.dynamodb import DynamoDb, le_filter
from pending_event import PendingEventType, PendingEvent
from repos import QueryResult
from repos.aws import PENDING_EVENT_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.pending_event_repo import PendingEventsRepo
from utils import loghelper
from utils.date_utils import get_system_time_in_millis, millis_to_timestamp

ACTIVE_AT = 'activeAt'

logger = loghelper.get_logger(__name__)

_MAX_TENANT_ID = 999999999999


class AwsPendingEventsRepo(AwsVirtualRangeTableRepo, PendingEventsRepo):
    __hash_key_attributes__ = {
        'eventType': str
    }

    __range_key_attributes__ = {
        ACTIVE_AT: (int, 19),
        'tenantId': (int, 12),
        'sessionId': str
    }
    __initializer__ = PendingEvent.from_record
    __virtual_table__ = PENDING_EVENT_TABLE

    def __init__(self, ddb: DynamoDb):
        super(AwsPendingEventsRepo, self).__init__(ddb)

    def query_events(self, event_type: PendingEventType, limit: int, next_token: Any) -> QueryResult:
        assert 0 < limit < 100000
        now = get_system_time_in_millis()
        results = QueryResult([], next_token)
        # This madness is because we have a composite range key, and we want to query by the first part of it.
        filter_op = le_filter(None, (now, _MAX_TENANT_ID, "X"))

        result = self.query(
            event_type.value,
            consistent=True,
            limit=limit,
            last_evaluated_key=results.next_token,
            range_filter=filter_op
        )
        results.rows.extend(result.rows)
        results.next_token = result.next_token

        return results

    def update_action_time(self, event: PendingEvent, seconds_in_future: int) -> bool:
        now = get_system_time_in_millis()
        new_action_at = now + (seconds_in_future * 1000)
        new_event = copy(event)
        new_event.active_at = new_action_at
        new_event.update_time = now

        logger.info(f"Setting action time for {event} to {millis_to_timestamp(new_action_at)}.")

        # Since the action time is in the range key, we need to remove the current record and create a new one
        del_req = self.create_delete_item_request(event, must_exist=True)
        put_req = self.create_put_item_request(new_event)
        bad_req = self.transact_write([del_req, put_req])
        if bad_req is not None:
            return False
        event.active_at = new_action_at
        event.update_time = now
        return True

    def update_action_times(self, events: Iterable[PendingEvent], seconds_in_future: int):
        target = get_system_time_in_millis() + (seconds_in_future * 1000)
        patches = {'activeAt': target}

        def construct(event: PendingEvent):
            return self.create_put_item_request(event, **patches)

        requests = list(map(construct, events))
        if len(requests) > 0:
            self.batch_write(requests)

    def delete_event(self, event: PendingEvent) -> bool:
        return self.delete_entry(event)
