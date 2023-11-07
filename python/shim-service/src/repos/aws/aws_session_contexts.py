from typing import Optional, List

from aws.dynamodb import DynamoDb, TransactionRequest, UpdateItemRequest
from bean import BeanSupplier
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
from services.sfdc.sfdc_session import SfdcSession
from session import Session, SessionStatus, ContextType, SessionContext, SessionKey
from utils import loghelper
from utils.date_utils import get_system_time_in_seconds

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
                 sequence_repo: AwsSequenceRepo,
                 sessions_repo_supplier: BeanSupplier[AwsSessionsRepo],
                 sfdc_sessions_repo_supplier: BeanSupplier[AwsSfdcSessionsRepo],
                 pending_event_repo_supplier: BeanSupplier[AwsPendingEventsRepo]):
        super(AwsSessionContextsRepo, self).__init__(ddb)
        self.sequence_repo = sequence_repo
        self.sessions_repo_supplier = sessions_repo_supplier
        self.sfdc_sessions_repo_supplier = sfdc_sessions_repo_supplier
        self.pending_event_repo_supplier = pending_event_repo_supplier

    def create_session_context(self, context: SessionContext) -> bool:
        return self.create(context)

    def __construct_create_requests(self, session: Session,
                                    sfdc_session: SfdcSession,
                                    contexts: List[SessionContext]):
        requests = list(map(lambda c: self.create_put_item_request(c), contexts))
        sfdc_repo: AwsSfdcSessionsRepo = self.sfdc_sessions_repo_supplier.get()
        requests.append(
            sfdc_repo.create_put_request(sfdc_session, get_system_time_in_seconds() + session.expiration_seconds))

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
                                sfdc_session: SfdcSession,
                                contexts: List[SessionContext]) -> bool:
        requests = self.__construct_create_requests(session, sfdc_session, contexts)

        bad_req: TransactionRequest = self.sequence_repo.execute_with_event(
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
