from typing import Optional, Any, List, Union, Dict, Callable

from retry import retry

from aws.dynamodb import DynamoDb, TransactionRequest
from events import Event
from events.event_types import EventType
from repos import OptimisticLockException
from repos.aws import SEQUENCE_TABLE
from repos.aws.abstract_table_repo import AwsVirtualTableRepo
from repos.aws.aws_events import AwsEventsRepo
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


class RequestData:
    def __init__(self, request: TransactionRequest, event_data: dict):
        self.request = request
        self.event_data = event_data


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
    def __get_current_sequence(self, tenant_id: int,
                               name: str,
                               max_lock_seconds: int,
                               auto_increment: bool = True) -> Sequence:
        current: Optional[Sequence] = self.find(tenant_id, name, consistent=True)
        next_timeout = date_utils.get_epoch_seconds_in_future(max_lock_seconds)
        if current is None:
            current = Sequence(tenant_id, name, 2, next_timeout)
            if not self.create(current):
                raise OptimisticLockException()
            current.next_value = 1 if auto_increment else 0
        else:
            if current.timeout_at > 0 and get_system_time_in_seconds() < current.timeout_at:
                raise OptimisticLockException()
            patches = {} if not auto_increment else {'nextValue': current.next_value + 1}
            self.patch_with_condition(
                current,
                "timeoutAt", next_timeout,
                patches
            )
        return Sequence(tenant_id, name, current.next_value, next_timeout)

    def execute_with_events(self,
                            tenant_id: int,
                            event_type: EventType,
                            num_requests: int,
                            data_creator: Callable[[int], RequestData],
                            max_lock_seconds: int = 30):
        # Max is 100, we need an event for each request, so we can't allow more than 50 here.
        assert num_requests < 50
        seq_update = self.__get_current_sequence(tenant_id, 'EventSeq', max_lock_seconds)
        original = seq_update.next_value
        good = False
        try:
            request_list = []
            for i in range(num_requests):
                seq_update.next_value += 1
                data = data_creator(seq_update.next_value)
                event = Event(
                    tenant_id,
                    seq_update.next_value,
                    event_type,
                    uuid(),
                    data.event_data
                )
                request_list.append(self.events_repo.create_put_item_request(event))
                request_list.append(data.request)
            bad_req = self.transact_write(request_list)
            good = bad_req is None
            return bad_req
        finally:
            if not good:
                seq_update.next_value = original
            self.patch_with_condition(
                seq_update,
                "timeoutAt",
                0
            )

    def execute_with_event(self, tenant_id: int,
                           request_list: List[TransactionRequest],
                           event_type: EventType,
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

        additional_requests = self.events_repo.examine_event(event)

        def inner(seq_no: int):
            nonlocal request_list
            event.seq_no = seq_no
            request_list.append(self.events_repo.create_put_item_request(event))
            if seq_no_listener is not None:
                seq_no_listener(seq_no)
            if additional_requests is not None:
                request_list = list(request_list)
                request_list.extend(additional_requests)
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
