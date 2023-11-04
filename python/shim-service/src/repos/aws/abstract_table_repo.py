import abc
from typing import Dict, Any

from farmhash import FarmHash64

from aws.dynamodb import DynamoDb
from repos import Record
from repos.aws import VIRTUAL_HASH_KEY, VIRTUAL_RANGE_KEY, SHIM_SERVICE_VIRTUAL_TABLE
from repos.aws.abstract_repo import AbstractAwsRepo

MAX_PARTITIONS = 64


class AbstractVirtualTableRepo(AbstractAwsRepo, metaclass=abc.ABCMeta):
    def __init__(self, ddb: DynamoDb):
        super(AbstractVirtualTableRepo, self).__init__(ddb, self.get_attribute('__virtual_table__'))
        self.include_scan_index = self.find_attribute('__include_scan_index__', False)

    def prepare_item(self, entry: Record) -> Dict[str, Any]:
        item = super().prepare_item(entry)
        if self.include_scan_index:
            # Here we populate the 'sk' attribute we use for 'scanning'
            if self.include_scan_index:
                sk = self.virtual_table.table_type
                hv = item[VIRTUAL_HASH_KEY]
                if self.primary_key.key_count() > 1:
                    hv += f"#{item[VIRTUAL_RANGE_KEY]}"
                partition_id = FarmHash64(hv) % MAX_PARTITIONS
                if partition_id < 0:
                    partition_id = -partition_id
                sk = f"{self.virtual_table.table_type}#{partition_id}"
                item['sk'] = sk

        return item


class AwsVirtualTableRepo(AbstractVirtualTableRepo):
    """
    Used as a base class for all Virtual tables that do NOT need a range key.
    """
    __table_name__ = SHIM_SERVICE_VIRTUAL_TABLE
    __hash_key__ = VIRTUAL_HASH_KEY

    def __init__(self, ddb: DynamoDb):
        super(AwsVirtualTableRepo, self).__init__(ddb)
