import json
from copy import deepcopy
from typing import List

from aws.dynamodb import _to_ddb_item
from base_test import BaseTest, AsyncMode, PUBSUB_TOPIC, DEFAULT_USER_ID
from bean import beans, BeanName
from mocks.pubsub_service_mock import PubSubServiceMock, MockResponder, convert_replay_id
from poll.base_processor import BasePollingProcessor
from poll.platform_event import ContextSettings
from push_notification import SessionPushNotification
from repos.aws.aws_work_id_map_repo import AwsWorkIdRepo
from repos.session_push_notifications import SessionPushNotificationsRepo
from repos.work_id_map_repo import WorkIdMap
from session import Session
from support.dict_stuff import replace_properties_in_dict
from table_listener.processor import TableListenerProcessor
from tenant import TenantContextType
from tenant.repo import TenantContextRepo
from utils.string_utils import uuid

RECORD_TEMPLATE = {
    "eventID": "${eventId}",
    "eventName": "INSERT",
    "eventVersion": "1.1",
    "eventSource": "aws:dynamodb",
    "awsRegion": "us-west-1",
    "dynamodb": {
        "ApproximateCreationDateTime": 1700180973,
        "Keys": {
            "tenantId": {
                "N": "${tenantId}"
            },
            "sessionId": {
                "S": "${sessionId}"
            }
        },
        "NewImage": {

        },
        "SequenceNumber": "30864200000000007273626025",
        "SizeBytes": 57,
        "StreamViewType": "KEYS_ONLY"
    },
    "eventSourceARN": "arn:aws:dynamodb:us-west-1:433933949595:table/ShimServiceSession/stream/2023-11-16T22:14:15.335"

}

_USER_ID_FIELD = 'RS_L__User_Id__c'
_CONVERSATION_ID_FIELD = 'RS_L__Conversation_Id__c'
_MESSAGE_TYPE_FIELD = 'RS_L_Type__c'
_MESSAGE_FIELD = 'RS_L_Message__c'


class PubSubProcessorSuite(BaseTest):
    processor: BasePollingProcessor
    table_listener_processor: TableListenerProcessor
    pubsub_service_mock: PubSubServiceMock
    responder: MockResponder

    def test_simple(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        sess = self.get_session_from_token(token)
        self.__add_response(user_id=DEFAULT_USER_ID, message_type='MESSAGE', message="Hello!")
        self.invoke(token)

        stub = self.pubsub_service_mock.pop_stub()
        self.assertTrue(stub.channel.closed)
        self.assertEqual('api.pubsub.salesforce.com:7443', stub.channel.host_and_port)

        # Grab the tenant context and make sure the replay id was saved properly
        context_repo: TenantContextRepo = beans.get_bean_instance(BeanName.TENANT_CONTEXT_REPO)
        context = context_repo.find_context(TenantContextType.X1440, sess.tenant_id)
        self.assertIsNotNone(context)
        settings = ContextSettings.deserialize(context.data)
        self.assertEqual(1, convert_replay_id(settings.replay_id))

        # look for the notification in the repo
        notifications = self.__query_notifications(sess)
        self.assertHasLength(1, notifications)
        n = notifications[0]
        self.assertEqual("MESSAGE", n.message_type)
        self.assertEqual("x1440", n.platform_channel_type)
        decoded = json.loads(n.message)
        self.assertEqual("Hello!", decoded[_MESSAGE_FIELD])
        self.assertEqual(DEFAULT_USER_ID, decoded[_USER_ID_FIELD])

        # Call again, we should see only the new notification
        self.__add_response(user_id=DEFAULT_USER_ID, message_type='MESSAGE', message="Hello Again!")
        self.invoke(token)
        stub = self.pubsub_service_mock.pop_stub()
        self.assertTrue(stub.channel.closed)
        notifications = self.__query_notifications(sess)
        self.assertHasLength(2, notifications)
        n = notifications[1]
        self.assertEqual("MESSAGE", n.message_type)
        self.assertEqual("x1440", n.platform_channel_type)
        decoded = json.loads(n.message)
        self.assertEqual("Hello Again!", decoded[_MESSAGE_FIELD])
        self.assertEqual(DEFAULT_USER_ID, decoded[_USER_ID_FIELD])

        # Call invoke again, it should not notify because the replay id is now 2
        self.invoke(token)
        stub = self.pubsub_service_mock.pop_stub()
        self.assertTrue(stub.channel.closed)

        notifications = self.__query_notifications(sess)
        self.assertHasLength(2, notifications)

    def test_by_conversation_id(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        sess = self.get_session_from_token(token)
        # Let's fake a conversation id
        work_id_map_repo: AwsWorkIdRepo = beans.get_bean_instance(BeanName.WORK_ID_MAP_REPO)
        work = WorkIdMap(sess.tenant_id, DEFAULT_USER_ID, 'workId', 'conversationId', sess.session_id)
        work_id_map_repo.create(work)
        self.__add_response(conversation_id='conversationId', message_type='MESSAGE', message="Hello!")
        self.invoke(token)
        stub = self.pubsub_service_mock.pop_stub()
        self.assertTrue(stub.channel.closed)

        notifications = self.__query_notifications(sess)
        self.assertEqual(1, len(notifications))
        n = notifications[0]
        decoded = json.loads(n.message)
        self.assertEqual("Hello!", decoded[_MESSAGE_FIELD])

    @staticmethod
    def __query_notifications(sess: Session) -> List[SessionPushNotification]:
        repo: SessionPushNotificationsRepo = beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_REPO)
        return list(repo.query_notifications(sess))

    def __add_response(self, user_id: str = None, conversation_id: str = None, message_type: str = None,
                       message: str = None, **kwargs):
        record = {}
        if user_id is not None:
            record[_USER_ID_FIELD] = user_id
        if conversation_id is not None:
            record[_CONVERSATION_ID_FIELD] = conversation_id
        if message_type is not None:
            record[_MESSAGE_TYPE_FIELD] = message_type
        if message is not None:
            record[_MESSAGE_FIELD] = message
        record.update(kwargs)
        self.responder.add_notification(PUBSUB_TOPIC, record)

    def invoke(self, token: str):
        sess = self.get_session_from_token(token)
        record = deepcopy(RECORD_TEMPLATE)
        record = replace_properties_in_dict(record,
                                            {
                                                'eventId': uuid(),
                                                'tenantId': sess.tenant_id,
                                                'sessionId': sess.session_id
                                            })
        item = _to_ddb_item(sess.to_record())
        record['dynamodb']['NewImage'].update(item)
        self.table_listener_processor.invoke({'Records': [record]})
        self.processor.invoke({})

    def setUp(self) -> None:
        super().setUp()
        self.pubsub_service_mock = PubSubServiceMock()
        beans.override_bean(BeanName.PUBSUB_SERVICE, self.pubsub_service_mock)
        self.processor = beans.get_bean_instance(BeanName.PUBSUB_POLLER_PROCESSOR)
        self.table_listener_processor = beans.get_bean_instance(BeanName.TABLE_LISTENER_PROCESSOR)
        self.responder = self.pubsub_service_mock.responder
