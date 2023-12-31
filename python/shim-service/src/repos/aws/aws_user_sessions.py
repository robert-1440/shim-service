from typing import Optional

from aws.dynamodb import DynamoDb
from repos.aws import USER_SESSION_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.user_sessions import UserSessionsRepo
from session import UserSession


class AwsUserSessionsRepo(AwsVirtualRangeTableRepo, UserSessionsRepo):
    __hash_key_attributes__ = {
        'tenantId': int,
    }

    __range_key_attributes__ = {
        'userId': str
    }
    __initializer__ = UserSession.from_record
    __virtual_table__ = USER_SESSION_TABLE

    def __init__(self, ddb: DynamoDb):
        super(AwsUserSessionsRepo, self).__init__(ddb)

    def find_user_session(self, tenant_id: int, user_id: str) -> Optional[UserSession]:
        return self.find(tenant_id, user_id)

    def delete_user_session(self, tenant_id: int, user_id: str) -> bool:
        return self.delete(tenant_id, user_id)
