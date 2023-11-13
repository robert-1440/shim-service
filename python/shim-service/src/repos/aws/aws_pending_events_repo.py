from typing import Iterable, Any

from aws.dynamodb import DynamoDb, le_filter
from pending_event import PendingEventType, PendingEvent
from repos import QueryResult, OptimisticLockException
from repos.aws import PENDING_EVENT_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.pending_event_repo import PendingEventsRepo
from utils import loghelper
from utils.date_utils import get_system_time_in_millis, millis_to_timestamp

ACTIVE_AT = 'activeAt'

logger = loghelper.get_logger(__name__)

class AwsPendingEventsRepo(AwsVirtualRangeTableRepo, PendingEventsRepo):
    __hash_key_attributes__ = {
        'eventType': str
    }

    __range_key_attributes__ = {
        'eventTime': (int, 19),
        'tenantId': int,
        'sessionId': str
    }
    __initializer__ = PendingEvent.key_from_dict
    __virtual_table__ = PENDING_EVENT_TABLE

    def __init__(self, ddb: DynamoDb):
        super(AwsPendingEventsRepo, self).__init__(ddb)

    def query_events(self, event_type: PendingEventType, limit: int, next_token: Any) -> QueryResult:
        assert 0 < limit < 100000
        now = get_system_time_in_millis()
        results = QueryResult([], next_token)
        filter_op = le_filter('activeAt', now)
        while True:
            result = self.query(
                event_type.value,
                consistent=True,
                limit=limit,
                last_evaluated_key=results.next_token,
                filters=filter_op
            )
            results.rows.extend(result.rows)
            results.next_token = result.next_token
            limit -= len(result.rows)
            if result.next_token is None or limit == 0:
                break

        return results

    def update_action_time(self, event: PendingEvent, seconds_in_future: int) -> bool:
        new_action_at = get_system_time_in_millis() + (seconds_in_future * 1000)
        try:
            logger.info(f"Setting action time for {event} to {millis_to_timestamp(new_action_at)}.")
            self.patch_with_condition(event, ACTIVE_AT, new_action_at)
            event.active_at = new_action_at
            return True
        except OptimisticLockException:
            return False

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
