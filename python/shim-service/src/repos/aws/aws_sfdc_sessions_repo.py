from typing import Dict, Any, Optional

from aws.dynamodb import PutItemRequest, DynamoDb
from bean import BeanSupplier
from repos.aws import SFDC_SESSION_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.aws.abstract_repo import AbstractAwsRepo
from repos.sfdc_sessions_repo import SfdcSessionsRepo, SfdcSessionDataAndContext
from session import ContextType, SessionContext, SessionStatus, SessionKey
from session.exceptions import SessionNotActiveException
from utils.byte_utils import compress, decompress
from utils.date_utils import EpochSeconds


class LocalRecord:
    def __init__(self,
                 tenant_id: int,
                 session_id: str,
                 expire_time: EpochSeconds,
                 session_data: bytes
                 ):
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.expire_time = expire_time
        self.session_data = session_data

    def to_record(self) -> Dict[str, Any]:
        return {
            "tenantId": self.tenant_id,
            "sessionId": self.session_id,
            "expireTime": self.expire_time,
            "sessionData": self.session_data
        }

    @classmethod
    def from_record(cls, record: Dict[str, Any]):
        return cls(
            record['tenantId'],
            record['sessionId'],
            record['expireTime'],
            record['sessionData']
        )


class AwsSfdcSessionsRepo(AwsVirtualRangeTableRepo, SfdcSessionsRepo):
    __hash_key_attributes__ = {
        'tenantId': int,
    }

    __range_key_attributes__ = {
        'sessionId': str
    }

    __initializer__ = LocalRecord.from_record
    __virtual_table__ = SFDC_SESSION_TABLE

    def __init__(self, ddb: DynamoDb, contexts_repo: AbstractAwsRepo,
                 sessions_repo_supplier: BeanSupplier):
        super(AwsSfdcSessionsRepo, self).__init__(ddb)
        self.contexts_repo = contexts_repo
        self.sessions_repo_supplier = sessions_repo_supplier

    def create_put_request(self, session_key: SessionKey, session_data: bytes, expire_time: EpochSeconds) -> PutItemRequest:
        record = LocalRecord(
            session_key.tenant_id,
            session_key.session_id,
            expire_time,
            compress(session_data)
        )
        return self.create_put_item_request(record)

    def create_patch_request(self, tenant_id: int, session_id: str, patch: Dict[str, Any],
                             must_exist: bool = True):
        return self.create_update_item_request_from_args(patch, tenant_id, session_id, must_exist=must_exist)

    def load_data(self, session_key: SessionKey) -> Optional[bytes]:
        record: LocalRecord = self.find(session_key.tenant_id, session_key.session_id)
        return decompress(record.session_data) if record is not None else None

    def load_data_and_context(self,
                              session_key: SessionKey,
                              context_type: ContextType,
                              consistent: bool = True) -> Optional[SfdcSessionDataAndContext]:
        session_req = self.sessions_repo_supplier.get().create_get_item_request_from_args(
            session_key.tenant_id,
            session_key.session_id,
            consistent=consistent,
            attributes_to_get=['sessionStatus', 'expSeconds']
        )

        our_req = self.create_get_item_request_from_args(
            session_key.tenant_id,
            session_key.session_id,
            consistent=consistent
        )
        context_req = self.contexts_repo.create_get_item_request_from_args(
            session_key.tenant_id,
            session_key.session_id,
            context_type.value,
            consistent=consistent
        )
        result = self.batch_get([session_req, our_req, context_req])
        if result.row_count != 3:
            return None

        sess_item = result.get_next_entry()
        if sess_item['sessionStatus'] != SessionStatus.ACTIVE.value:
            raise SessionNotActiveException()

        our_record: LocalRecord = result.get_next_entry()
        context_record: SessionContext = result.get_next_entry()

        return SfdcSessionDataAndContext(
            sess_item['expSeconds'],
            decompress(our_record.session_data),
            context_record
        )
