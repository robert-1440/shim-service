from typing import Optional, List, Dict, Any, Iterable

from aws.dynamodb import DynamoDb, TransactionRequest, GetItemRequest, le_filter, eq_filter
from events.event_types import EventType
from lambda_web_framework.web_exceptions import EntityExistsException
from repos import QueryResultSet
from repos.aws import SHIM_SERVICE_SESSION_TABLE
from repos.aws.abstract_repo import AbstractAwsRepo
from repos.aws.aws_events import AwsEventsRepo
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_sfdc_sessions_repo import AwsSfdcSessionsRepo
from repos.aws.aws_user_sessions import AwsUserSessionsRepo
from repos.sessions_repo import SessionsRepo, CreateSessionRequest, UserSessionExistsException
from session import Session, SessionKey, SessionStatus
from utils import loghelper
from utils.collection_utils import to_flat_list
from utils.date_utils import get_system_time_in_seconds

SESSION_ID = 'sessionId'

_TENANT_ID = "tenantId"
_SESSION_ID = "sessionId"

_EVENT_EXPIRATION_HOURS = 4
_EVENT_EXPIRATION_SECONDS = _EVENT_EXPIRATION_HOURS * 3600

logger = loghelper.get_logger(__name__)


class AwsSessionsRepo(SessionsRepo, AbstractAwsRepo):
    __table_name__ = SHIM_SERVICE_SESSION_TABLE
    __hash_key__ = _TENANT_ID
    __range_key__ = _SESSION_ID
    __initializer__ = Session.from_record
    __state_counter__ = True
    __update_time__ = True

    def __init__(self,
                 ddb: DynamoDb,
                 user_sessions_repo: AwsUserSessionsRepo,
                 events_repo: AwsEventsRepo,
                 sequence_repo: AwsSequenceRepo,
                 sfdc_sessions_repo: AwsSfdcSessionsRepo):
        super(AwsSessionsRepo, self).__init__(ddb)
        self.user_sessions_repo = user_sessions_repo
        self.events_repo = events_repo
        self.sequence_repo = sequence_repo
        self.sfdc_sessions_repo = sfdc_sessions_repo

    def create_session(self, request: CreateSessionRequest):
        expire_time = get_system_time_in_seconds() + request.session.expiration_seconds
        request.session.expiration_time = expire_time
        session_put = self.create_put_item_request(request.session)
        user_session = request.session.to_user_session()
        user_session_put = self.user_sessions_repo.create_put_item_request(user_session, expireTime=expire_time)

        requests = to_flat_list(session_put, user_session_put)

        bad_request: TransactionRequest = self.sequence_repo.execute_with_event(
            request.session.tenant_id,
            requests,
            EventType.SESSION_CREATED,
            event_data={
                'sessionId': request.session.session_id,
                'userId': request.session.user_id
            }
        )

        if bad_request is None:
            return None
        if id(bad_request) == id(user_session_put):
            sess = self.user_sessions_repo.find_user_session(request.session)
            if sess is not None:
                raise UserSessionExistsException(sess.session_id)
        logger.warning(f"Failed to create session: {request.session.describe()}: {bad_request.describe()}")

        raise EntityExistsException("Session already exists.")

    def find_session(self, session_key: SessionKey) -> Optional[Session]:
        return self.find(session_key.tenant_id, session_key.session_id, consistent=True)

    def update_session(self, session: Session) -> bool:
        requests = [self.create_update_with_state_check_request(session)]
        bad_request = self.sequence_repo.execute_with_event(
            session.tenant_id,
            requests,
            EventType.SESSION_UPDATED,
            event_data={
                'sessionId': session.session_id,
                'userId': session.user_id
            }
        )
        return bad_request is None

    def touch_with_event(self,
                         key: SessionKey,
                         user_id: str,
                         expiration_seconds: int,
                         event_type: EventType = EventType.SESSION_TOUCHED,
                         event_data: Optional[Dict[str, Any]] = None):
        expiration_time = get_system_time_in_seconds() + expiration_seconds
        patch = {'expireTime': expiration_time}
        event_data = dict(event_data) if event_data is not None else {}
        event_data.update({
            'sessionId': key.session_id,
            'userId': user_id
        })

        request_list = to_flat_list(
            self.create_update_item_request_from_args(patch, key.tenant_id, key.session_id,
                                                      must_exist=True),
            self.user_sessions_repo.create_update_item_request_from_args(patch, key.tenant_id, user_id,
                                                                         must_exist=True),
            self.sfdc_sessions_repo.create_patch_request(key.tenant_id, key.session_id, patch)
        )

        error_request: TransactionRequest = self.sequence_repo.execute_with_event(
            key.tenant_id,
            request_list,
            event_type,
            event_data
        )
        if error_request is not None:
            logger.warning(f"Error executing touch for {key}: '{error_request.describe()}")
            return None
        return expiration_time

    def delete_session(self, session: Session) -> bool:
        session_request = self.create_delete_item_request_from_args(
            session.tenant_id,
            session.session_id,
            must_exist=True
        )
        user_session_request = self.user_sessions_repo.create_delete_item_request_from_args(
            session.tenant_id,
            session.user_id
        )
        error_request = self.sequence_repo.execute_with_event(
            session.tenant_id,
            to_flat_list(session_request, user_session_request),
            EventType.SESSION_DELETED,
            event_data={
                'sessionId': session.session_id,
                'userId': session.user_id
            }
        )
        if error_request is not None:
            logger.error(f"Failed to delete session {session.tenant_id}-{session.session_id}: "
                         f"{error_request.cancel_reason}")
            return False
        return True

    def fix_orphaned_user_session(self, session: Session):
        requests = to_flat_list(
            self.user_sessions_repo.create_delete_item_request_from_args(session.tenant_id, session.user_id),
        )
        self.ddb.batch_write(requests)

    def create_get_item_request_from_key(self, key: SessionKey,
                                         consistent: bool = False,
                                         attributes_to_get: List[str] = None) -> GetItemRequest:
        return self.create_get_item_request_from_args(
            key.tenant_id,
            key.session_id,
            consistent=consistent,
            attributes_to_get=attributes_to_get
        )

    def has_sessions_with_platform_channel_type(self, tenant_id: int, channel_type: str):
        # where status = 'A' and p_channel_type = True
        status_filter = eq_filter('sessionStatus', SessionStatus.ACTIVE.value)
        channel_filter = eq_filter(f'pt_{channel_type}', True)
        result_set = self.query_set(
            tenant_id,
            consistent=True,
            count_only=True,
            filters=(status_filter, channel_filter)
        )

        for _ in result_set:
            return True
        return False

    def query_session_ids_with_platform_channel_type(self,
                                                     tenant_id: int,
                                                     channel_type: str) -> Iterable[str]:

        status_filter = eq_filter('sessionStatus', SessionStatus.ACTIVE.value)
        channel_filter = eq_filter(f'pt_{channel_type}', True)
        result_set = self.query_set(
            tenant_id,
            consistent=True,
            select_attributes=[SESSION_ID],
            filters=(status_filter, channel_filter)
        )
        return map(lambda r: r[SESSION_ID], result_set)
