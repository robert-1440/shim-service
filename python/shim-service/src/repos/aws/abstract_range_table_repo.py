from aws.dynamodb import DynamoDb
from repos.aws import VIRTUAL_HASH_KEY, VIRTUAL_RANGE_KEY, SHIM_SERVICE_VIRTUAL_RANGE_TABLE
from repos.aws.abstract_table_repo import AbstractVirtualTableRepo


class AwsVirtualRangeTableRepo(AbstractVirtualTableRepo):
    """
    Used as a base class for all virtual tables that need a range key.
    """
    __table_name__ = SHIM_SERVICE_VIRTUAL_RANGE_TABLE
    __hash_key__ = VIRTUAL_HASH_KEY
    __range_key__ = VIRTUAL_RANGE_KEY

    def __init__(self, ddb: DynamoDb):
        super(AwsVirtualRangeTableRepo, self).__init__(ddb)
        assert self.primary_key.key_count() == 2, "Range key is required"
