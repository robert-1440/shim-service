from typing import Dict, Any, Optional, Iterable

from aws.dynamodb import DynamoDb, not_exists_filter, TransactionRequest
from events import event_types
from lambda_pkg import LambdaInvoker
from lambda_web_framework.web_exceptions import ConflictException
from push_notification import SessionPushNotification
from repos.aws import PUSH_NOTIFICATION_TABLE
from repos.aws.abstract_range_table_repo import AwsVirtualRangeTableRepo
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_session_contexts import AwsSessionContextsRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from session import SessionContext, SessionKey
from utils import string_utils, loghelper
from utils.date_utils import EpochMilliseconds, get_system_time_in_millis

logger = loghelper.get_logger(__name__)


class LocalRecord:
    def __init__(self, tenant_id: int,
                 session_id: str,
                 seq_no: int,
                 channel_type: str,
                 message_type: str,
                 message_data: Optional[bytes],
                 time_created: EpochMilliseconds,
                 sent: bool):
        self.tenant_id = tenant_id
        self.session_id = session_id
        self.seq_no = seq_no
        self.channel_type = channel_type
        self.message_type = message_type
        self.message_data = message_data
        self.time_created = time_created
        self.sent = sent

    def to_notification(self) -> SessionPushNotification:
        if self.message_data is not None:
            message_data = string_utils.decompress(self.message_data)
        else:
            message_data = None
        return SessionPushNotification(
            self.tenant_id,
            self.session_id,
            self.seq_no,
            self.channel_type,
            self.message_type,
            message_data,
            self.time_created,
            self.sent
        )

    def to_record(self) -> Dict[str, Any]:
        record = {
            'tenantId': self.tenant_id,
            'sessionId': self.session_id,
            'seqNo': self.seq_no,
            'channelType': self.channel_type,
            'timeCreated': self.time_created
        }
        if self.message_type is not None:
            record['messageType'] = self.message_type
        if self.message_data is not None:
            record['messageData'] = self.message_data
        if self.sent:
            record['sent'] = True
        return record

    @classmethod
    def from_record(cls, record: Dict[str, Any]) -> 'LocalRecord':
        return cls(
            record['tenantId'],
            record['sessionId'],
            record['seqNo'],
            record['channelType'],
            record.get('messageType'),
            record.get('messageData'),
            record['timeCreated'],
            record.get('sent')
        )

    @classmethod
    def from_entry(cls, n: SessionPushNotification) -> 'LocalRecord':
        return cls(
            n.tenant_id,
            n.session_id,
            n.seq_no,
            n.platform_channel_type,
            n.message_type,
            string_utils.compress(n.message),
            n.time_created,
            n.sent
        )


class AwsPushNotificationsRepo(AwsVirtualRangeTableRepo, SessionPushNotificationsRepo):
    __hash_key_attributes__ = {
        'tenantId': int,
        'sessionId': str
    }

    __range_key_attributes__ = {
        'seqNo': (int, 16)
    }

    __initializer__ = LocalRecord.from_record
    __virtual_table__ = PUSH_NOTIFICATION_TABLE

    def __init__(self, ddb: DynamoDb,
                 sequence_repo: AwsSequenceRepo,
                 session_contexts_repo: AwsSessionContextsRepo,
                 lambda_invoker: LambdaInvoker):
        super(AwsPushNotificationsRepo, self).__init__(ddb)
        self.sequence_repo = sequence_repo
        self.session_contexts_repo = session_contexts_repo
        self.lambda_invoker = lambda_invoker

    def submit(self, context: SessionContext, platform_channel_type: str, message_type: str, message: str):
        record = LocalRecord(
            context.tenant_id,
            context.session_id,
            0,
            channel_type=platform_channel_type,
            message_type=message_type,
            message_data=string_utils.compress(message),
            time_created=get_system_time_in_millis(),
            sent=False
        )
        request_list: Any = [None]

        def seq_no_assigned(seq_no: int):
            record.seq_no = seq_no
            request_list[0] = self.create_put_item_request(record)

        bad_event: TransactionRequest = self.sequence_repo.execute_with_event(
            context.tenant_id,
            request_list,
            event_types.PUSH_NOTIFICATION,
            event_data={
                'sessionId': context.session_id,
                'userId': context.user_id,
                'platformChannelType': platform_channel_type,
                'messageType': message_type
            },
            seq_no_listener=seq_no_assigned
        )
        if bad_event is not None:
            raise ConflictException(f"Failed to submit push notification: {bad_event.cancel_reason}")
        self.lambda_invoker.invoke_notification_poller(context)

    def query_notifications(self,
                            session_key: SessionKey,
                            previous_seq_no: int = None) -> Iterable[SessionPushNotification]:
        rset = self.query_set(
            session_key.tenant_id,
            session_key.session_id,
            consistent=True,
            start_after=previous_seq_no,
            filters=not_exists_filter('sent')
        )
        return map(lambda r: r.to_notification(), rset)

    def set_sent(self, record: SessionPushNotification, context: SessionContext = None) -> bool:
        local_record = LocalRecord.from_entry(record)
        patches = {'sent': True}
        if context is None:
            return self.patch(local_record, patches)
        else:
            req = self.create_update_item_request(local_record, patches=patches)
            context_req = self.session_contexts_repo.create_patch_session_data_request(context)
            bad_req = self.transact_write([req, context_req])
            if bad_req is not None:
                logger.warning(f"Failed to update context {context}: {bad_req.cancel_reason}")
                return False
            return True
