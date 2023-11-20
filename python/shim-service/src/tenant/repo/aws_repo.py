from typing import Any

from retry import retry

from aws.dynamodb import DynamoDb, le_filter
from repos import OptimisticLockException, QueryResult
from repos.aws import PENDING_TENANT_EVENT_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from tenant import PendingTenantEvent, PendingTenantEventType
from tenant.repo import PendingTenantEventRepo
from utils.date_utils import get_system_time_in_millis

ACTIVE_AT = 'activeAt'


class AwsPendingTenantEventRepo(AwsVirtualRangeTableRepo, PendingTenantEventRepo):
    __hash_key_attributes__ = {
        'eventType': str
    }

    __range_key_attributes__ = {
        'tenantId': (int, 12)
    }
    __initializer__ = PendingTenantEvent.from_record
    __virtual_table__ = PENDING_TENANT_EVENT_TABLE

    def __init__(self, ddb: DynamoDb):
        super().__init__(ddb)

    @retry(exceptions=OptimisticLockException, tries=10, delay=0.1, backoff=2)
    def update_or_create(self, entry: PendingTenantEvent):
        current = self.find(entry.event_type.value, entry.tenant_id, consistent=True)
        if current is None:
            if not self.create(entry):
                raise OptimisticLockException()
        else:
            if not self.patch_with_condition(current, 'stateCounter', entry.state_counter + 1, {}):
                raise OptimisticLockException()

    def update_action_time(self, event: PendingTenantEvent, seconds_in_future: int) -> bool:
        now = get_system_time_in_millis()
        new_action_at = now + (seconds_in_future * 1000)
        if self.patch_with_condition(event, ACTIVE_AT, new_action_at, {}):
            event.active_at = new_action_at
            return True
        return False

    def delete_event(self, event: PendingTenantEvent) -> bool:
        return self.delete_with_condition(event, 'stateCounter', event.state_counter)

    def query_events(self, event_type: PendingTenantEventType, limit: int, next_token: Any) -> QueryResult:
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
