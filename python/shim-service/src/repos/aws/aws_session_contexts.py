import json
from typing import Optional, List

from aws.dynamodb import DynamoDb, TransactionRequest, UpdateItemRequest, DynamoDbRow, DynamoDbItem, _from_ddb_item
from bean import BeanSupplier
from config import Config
from events.event_types import EventType
from pending_event import PendingEventType, PendingEvent
from repos import Serializable
from repos.aws import SESSION_CONTEXT_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.aws.aws_pending_events_repo import AwsPendingEventsRepo
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_sessions import AwsSessionsRepo
from repos.aws.aws_sfdc_sessions_repo import AwsSfdcSessionsRepo
from repos.session_contexts import SessionContextsRepo, SessionContextAndFcmToken
from session import Session, SessionStatus, ContextType, SessionContext, SessionKey
from utils import loghelper, collection_utils, threading_utils
from utils.date_utils import get_system_time_in_seconds
from utils.exception_utils import dump_ex

logger = loghelper.get_logger(__name__)


class AwsSessionContextsRepo(AwsVirtualRangeTableRepo, SessionContextsRepo):
    __hash_key_attributes__ = {
        'tenantId': int,
    }

    __range_key_attributes__ = {
        'sessionId': str,
        'contextType': str
    }

    __initializer__ = SessionContext.from_record
    __virtual_table__ = SESSION_CONTEXT_TABLE

    def __init__(self, ddb: DynamoDb,
                 sequence_repo_supplier: BeanSupplier[AwsSequenceRepo],
                 sessions_repo_supplier: BeanSupplier[AwsSessionsRepo],
                 sfdc_sessions_repo_supplier: BeanSupplier[AwsSfdcSessionsRepo],
                 pending_event_repo_supplier: BeanSupplier[AwsPendingEventsRepo],
                 config: Config):
        super(AwsSessionContextsRepo, self).__init__(ddb)
        self.sequence_repo_supplier = sequence_repo_supplier
        self.sessions_repo_supplier = sessions_repo_supplier
        self.sfdc_sessions_repo_supplier = sfdc_sessions_repo_supplier
        self.pending_event_repo_supplier = pending_event_repo_supplier
        self.expiration_seconds = config.max_context_ttl_seconds

    def create_session_context(self, context: SessionContext) -> bool:
        return self.create(context)

    def prepare_put(self, item: DynamoDbRow):
        item['expireTime'] = get_system_time_in_seconds() + self.expiration_seconds

    def __construct_create_requests(self, session: Session,
                                    session_data: bytes,
                                    contexts: List[SessionContext]):
        requests = list(map(lambda c: self.create_put_item_request(c), contexts))
        sfdc_repo: AwsSfdcSessionsRepo = self.sfdc_sessions_repo_supplier.get()
        requests.append(
            sfdc_repo.create_put_request(session, session_data,
                                         get_system_time_in_seconds() + session.expiration_seconds))

        sess_repo = self.sessions_repo_supplier.get()
        requests.append(sess_repo.create_patch_with_state_check_request(session, {
            'sessionStatus': SessionStatus.ACTIVE.value
        }))

        if session.has_live_agent_polling():
            pe_repo = self.pending_event_repo_supplier.get()
            event = PendingEvent(
                PendingEventType.LIVE_AGENT_POLL,
                session.tenant_id,
                session.session_id
            )
            requests.append(pe_repo.create_put_item_request(event))

        return requests

    def create_session_contexts(self,
                                session: Session,
                                session_data: bytes,
                                contexts: List[SessionContext]) -> bool:
        requests = self.__construct_create_requests(session, session_data, contexts)

        bad_req: TransactionRequest = self.sequence_repo_supplier.get().execute_with_event(
            session.tenant_id,
            requests,
            EventType.SESSION_ACTIVATED,
            event_data={
                'sessionId': session.session_id,
                'userId': session.user_id,
                'channelPlatformTypes': session.channel_platform_types
            }
        )
        if bad_req is not None:
            logger.warning(f"Error creating session contexts for tenant_id={session.tenant_id}, "
                           f"session_id={session.session_id} - {bad_req.describe()}")
            return False
        return True

    def find_session_context(self,
                             session_key: SessionKey,
                             context_type: ContextType) -> Optional[SessionContext]:
        return self.find(session_key.tenant_id, session_key.session_id, context_type.value)

    def find_session_context_with_fcm_token(self,
                                            session_key: SessionKey,
                                            context_type: ContextType) -> Optional[SessionContextAndFcmToken]:
        ctx_req = self.create_get_item_request_from_args(
            session_key.tenant_id,
            session_key.session_id,
            context_type.value
        )
        sess_req = self.sessions_repo_supplier.get().create_get_item_request_from_key(session_key,
                                                                                      consistent=True,
                                                                                      attributes_to_get=[
                                                                                          "sessionStatus",
                                                                                          "fcmDeviceToken"])
        results = self.batch_get([ctx_req, sess_req])
        if results.row_count > 0:
            ctx: SessionContext = results.get_entry_at(0)
            if ctx is not None:
                atts = results.get_entry_at(1)
                if atts is None or atts['sessionStatus'] == SessionStatus.FAILED.value:
                    return SessionContextAndFcmToken(ctx, None)
                return SessionContextAndFcmToken(ctx, atts['fcmDeviceToken'])

        return None

    def update_session_context(self, context: SessionContext, new_data: Serializable = None) -> bool:
        if new_data is not None:
            serialized = new_data.serialize()
            if serialized == context.session_data:
                return True
            new_bytes = serialized
        else:
            new_bytes = context.session_data
        return self.patch(context, {'sessionData': new_bytes})

    def delete_session_context(self,
                               session_key: SessionKey,
                               context_type: ContextType) -> bool:
        return self.delete(session_key.tenant_id, session_key.session_id, context_type.value)

    def set_failed(self, context: SessionContext, message: str, pending_event: PendingEvent = None) -> bool:
        sess_repo = self.sessions_repo_supplier.get()
        sess_req = sess_repo.create_patch_from_args_request(context.tenant_id, context.session_id, patches={
            'sessionStatus': SessionStatus.FAILED.value,
            'failureMessage': message
        }, must_exist=False)

        requests = [sess_req]
        for ct in ContextType:
            requests.append(self.create_delete_item_request_from_args(context.tenant_id, context.session_id,
                                                                      ct.value))

        if pending_event is not None:
            requests.append(self.pending_event_repo_supplier.get().create_delete_item_request(pending_event))

        return self.transact_write(requests) is None

    def create_patch_session_data_request(self, context: SessionContext) -> UpdateItemRequest:
        return self.create_update_item_request(context, patches={'sessionData': context.session_data})

    def delete_by_row_keys(self, row_keys: List[DynamoDbItem]):

        def extend(rows: List[DynamoDbRow], row: DynamoDbItem):
            key = _from_ddb_item(row)
            for ct in ContextType:
                new_key = dict(key)
                new_key['contextType'] = ct.value
                # We are a virtual table, so we need to build the actual key
                rows.append(self.primary_key.build_key_as_dict(new_key))

        def submit(list_of_keys: List[DynamoDbRow]):
            try:
                logger.info(f"Attempting to delete {len(list_of_keys)} context record(s) ...")
                self.ddb.batch_delete_from_table(self.table_name, list_of_keys)
            except BaseException as ex:
                logger.error(f"Failed to delete batch: {dump_ex(ex)}")

        submit_list = []
        for row in row_keys:
            extend(submit_list, row)

        logger.info(f"Keys to delete: {json.dumps(submit_list, indent=True)})")
        if len(submit_list) < 25:
            submit(submit_list)
        else:
            threads = []
            for block in collection_utils.partition(submit_list, 25):
                threads.append(threading_utils.start_thread(submit, block))

            for t in threads:
                t.join(10)
