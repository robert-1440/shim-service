from typing import Optional, Any, List, Union, Dict

from retry import retry

from aws.dynamodb import DynamoDb, TransactionRequest
from repos import OptimisticLockException
from repos.aws import SEQUENCE_TABLE
from repos.aws.abstract_table_repo import AwsVirtualTableRepo
from repos.aws.aws_events import AwsEventsRepo
from repos.events import Event
from repos.sequences import SequenceRepo, SequenceCaller
from utils import date_utils
from utils.date_utils import get_system_time_in_seconds
from utils.string_utils import uuid


class Sequence:
    def __init__(self,
                 tenant_id: int,
                 name: str,
                 next_value: int,
                 timeout_at: Optional[int]):
        self.tenant_id = tenant_id
        self.name = name
        self.next_value = next_value
        self.timeout_at = timeout_at

    def to_record(self):
        return {
            'tenantId': self.tenant_id,
            'sequenceName': self.name,
            'nextValue': self.next_value,
            'timeoutAt': self.timeout_at
        }

    @classmethod
    def from_record(cls, record: dict):
        return cls(record['tenantId'], record['sequenceName'], record['nextValue'], record.get('timeoutAt'))


class AwsSequenceRepo(AwsVirtualTableRepo, SequenceRepo):
    __hash_key_attributes__ = {
        'tenantId': int,
        'sequenceName': str
    }
    __virtual_table__ = SEQUENCE_TABLE
    __initializer__ = Sequence.from_record

    def __init__(self, ddb: DynamoDb, events_repo: AwsEventsRepo):
        super(AwsSequenceRepo, self).__init__(ddb)
        self.events_repo = events_repo

    @retry(exceptions=OptimisticLockException, tries=20, delay=.5, max_delay=30, backoff=.1, jitter=(.1, .9))
    def __get_current_sequence(self, tenant_id: int, name: str, max_lock_seconds: int) -> Sequence:
        current: Optional[Sequence] = self.find(tenant_id, name, consistent=True)
        next_timeout = date_utils.get_epoch_seconds_in_future(max_lock_seconds)
        if current is None:
            current = Sequence(tenant_id, name, 2, next_timeout)
            if not self.create(current):
                raise OptimisticLockException()
            current.next_value = 1
        else:
            if current.timeout_at > 0 and get_system_time_in_seconds() < current.timeout_at:
                raise OptimisticLockException()
            self.patch_with_condition(
                current,
                "timeoutAt", next_timeout,
                {'nextValue': current.next_value + 1}
            )
        return Sequence(tenant_id, name, current.next_value, next_timeout)

    def execute_with_event(self, tenant_id: int,
                           request_list: List[TransactionRequest],
                           event_type: str,
                           event_data: Optional[Union[str, Dict]] = None,
                           event_id: str = None,
                           max_lock_seconds: int = 30,
                           seq_no_listener: SequenceCaller = None):
        event = Event(
            tenant_id,
            0,
            event_type,
            uuid() if event_id is None else event_id,
            event_data
        )

        def inner(seq_no: int):
            event.seq_no = seq_no
            request_list.append(self.events_repo.create_put_item_request(event))
            if seq_no_listener is not None:
                seq_no_listener(seq_no)
            return self.transact_write(request_list)

        return self.execute(tenant_id, 'EventSeq', max_lock_seconds, inner)

    def execute(self, tenant_id: int, name: str, max_lock_seconds: int, sequence_caller: SequenceCaller) -> Any:
        seq_update = self.__get_current_sequence(tenant_id, name, max_lock_seconds)
        try:
            return sequence_caller(seq_update.next_value)
        finally:
            self.patch_with_condition(
                seq_update,
                "timeoutAt",
                0
            )
