from typing import Optional, List

from aws.dynamodb import DynamoDb, TransactionRequest
from config import Config
from events import Event, EventType
from repos.aws import WORK_ID_MAP_TABLE
from repos.aws.abstract_table_repo import AwsVirtualTableRepo
from repos.aws.aws_events import EventListener
from repos.work_id_map_repo import WorkIdMapRepo, WorkIdMap
from utils.date_utils import get_system_time_in_seconds


class AwsWorkIdRepo(AwsVirtualTableRepo, WorkIdMapRepo, EventListener):
    __hash_key_attributes__ = {
        'tenantId': int,
        'workTargetId': str
    }

    __initializer__ = WorkIdMap.from_record
    __virtual_table__ = WORK_ID_MAP_TABLE

    def __init__(self, ddb: DynamoDb, config: Config):
        super(AwsWorkIdRepo, self).__init__(ddb)
        self.ttl_seconds = config.max_work_id_map_seconds

    def find_work_id(self, tenant_id: int, work_target_id: str) -> Optional[str]:
        entry: WorkIdMap = self.find(tenant_id, work_target_id)
        return entry.work_id if entry is not None else None

    def create_put_item_request_from_event(self, event: Event):
        event_data = event.data_record
        entry = WorkIdMap(event.tenant_id, event_data['workId'], event_data['workTargetId'])
        patch = {
            'workId': entry.work_id,
            'expire_time': get_system_time_in_seconds() + self.ttl_seconds
        }

        return self.create_update_item_request(
            entry,
            patch,
            must_exist=False
        )

    def event_received(self, event: Event, request_list: List[TransactionRequest]):
        if event.event_type == EventType.WORK_ACCEPTED:
            request_list.append(self.create_put_item_request_from_event(event))
