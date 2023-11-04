from aws.dynamodb import DynamoDb
from repos import QueryResult
from repos.aws import SHIM_SERVICE_EVENT_TABLE
from repos.aws.abstract_repo import AbstractAwsRepo
from repos.events import Event, EventsRepo


class AwsEventsRepo(AbstractAwsRepo, EventsRepo):
    __table_name__ = SHIM_SERVICE_EVENT_TABLE
    __hash_key__ = 'tenantId'
    __range_key__ = 'seqNo'

    __initializer__ = Event.from_record

    def __init__(self, ddb: DynamoDb):
        super(AwsEventsRepo, self).__init__(ddb)

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
