import json
from typing import Optional, Any, Dict

from base_test import BaseTest, AsyncMode, DEFAULT_WORK_ID, DEFAULT_WORK_TARGET_ID
from events import EventType
from mocks.extended_http_session_mock import ExtendedHttpMockSession
from mocks.http_session_mock import MockedResponse, MockHttpSession
from support.live_agent_helper import ONLINE_ID, BUSY_ID, OFFLINE_ID
from utils.http_client import HttpRequest
from utils.string_utils import uuid
from utils.validation_utils import MAX_DECLINE_REASON_LENGTH

ACCEPT_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/AcceptWork"
DECLINE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/DeclineWork"
CLOSE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/CloseWork"
CONVERSATION_END_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Conversational/ConversationEnd"
AFTER_CLOSE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/StartAfterConversationWork"
CONVERSATION_MESSAGE_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Conversational/ConversationMessage"


class PresenceTests(BaseTest):
    body_captured: dict
    sequence_counter: int

    def test_set_presence(self):

        session_token = self.create_web_session(async_mode=AsyncMode.NONE)

        # Let's test with invalid JSON to get some code coverage
        self.set_presence_status(
            session_token=session_token,
            raw_body="no good",
            expected_status_code=400,
            expected_error_message="Malformed JSON."
        )

        self.set_presence_status(
            session_token,
            'foo',
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'id' is invalid: 'foo' is invalid."
        )

        self.set_presence_status(
            session_token,
            status_id=ONLINE_ID
        )
        sess = self.get_session_from_token(session_token)

        events = self.query_events(sess, EventType.PRESENCE_STATUS_SET)
        self.assertHasLength(1, events)
        event = events[0]
        self.assertEqual('ONLINE', event.get_event_key('status'))
        self.assertEqual(sess.user_id, event.get_event_key('userId'))
        self.assertEqual(200, event.get_event_key('sfdcResponse'))

        self.assertEqual({
            'organizationId': 'the-org-id',
            'sfdcSessionId': 'the-session-id',
            'statusId': 'id1',
            'channelIdsWithParam': [
                {'channelId': 'agent'}, {'channelId': 'conversational'},
                {'channelId': 'lmagent'}
            ],
            'domain': 'somewhere.lightning.force.com'
        },
            self.body_captured)

        self.set_presence_status(
            session_token,
            status_id=BUSY_ID
        )
        events = self.query_events(sess, EventType.PRESENCE_STATUS_SET)
        self.assertEqual('BUSY', events[1].get_event_key('status'))

        self.assertEqual(BUSY_ID, self.body_captured['statusId'])
        self.set_presence_status(
            session_token,
            status_id=OFFLINE_ID
        )
        self.assertEqual(OFFLINE_ID, self.body_captured['statusId'])

        # We called it 3 times (the first one was rejected by the service not SFDC)
        self.assertEqual(3, self.sequence_counter)

        events = self.query_events(sess, EventType.PRESENCE_STATUS_SET)
        self.assertEqual('OFFLINE', events[2].get_event_key('status'))

    def test_accept_work(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.set_presence_status(
            token,
            status_id=ONLINE_ID
        )

        self.__accept_work(
            token,
            "bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workId' is invalid: value 'bad' is malformed - regex='^0Bz[a-zA-Z0-9]{12,15}'."
        )

        self.__accept_work(
            token,
            work_target_id="bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workTargetId' is invalid: value 'bad' has invalid length of 3, must be 15 or 18."
        )

        self.setup_mock_response(
            ACCEPT_WORK_URL,
            status_code=400,
            body={
                'sfErrorCode': "This is an error."
            }
        )

        self.__accept_work(
            token,
            expected_status_code=502,
            expected_error_message="SF call failed."
        )

        # For now, that last error sends a notification
        self.sns_mock.pop_notification('error:topic:arn')

        self.__accept_work(token)
        events = self.query_events_by_token(token, EventType.WORK_ACCEPTED)
        self.assertHasLength(2, events)
        self.assertEqual(400, events[0].get_event_key('sfdcResponse'))
        event = events[1]
        self.assertEqual(200, event.get_event_key('sfdcResponse'))
        self.assertEqual(DEFAULT_WORK_ID, event.get_event_key('workId'))
        self.assertEqual(DEFAULT_WORK_TARGET_ID, event.get_event_key('workTargetId'))

    def test_send_message_invalid_args(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.set_presence_status(
            token,
            status_id=ONLINE_ID
        )
        self.__accept_work(token)

        self.__send_work_message(
            token,
            work_target_id="bad",
            expected_status_code=404,
            expected_error_message="Resource Not Found: Unable to find specified workTargetId."
        )

        self.__send_work_message(
            token,
            expected_status_code=400,
            expected_error_message="Either messageBody or attachments must be specified."
        )

        self.__send_work_message(
            token,
            message="Hello",
            message_id="",
            expected_status_code=400,
            expected_error_message="Missing parameter 'id'."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments="none",
            expected_status_code=400,
            expected_error_message="'attachments' is invalid: invalid type."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments=['foo'],
            expected_status_code=400,
            expected_error_message="'attachments[0]' is invalid: invalid type."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments=[{'a': 1}],
            expected_status_code=400,
            expected_error_message="'attachments[0]' is invalid: Missing 'key'."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments=[{'key': 1}],
            expected_status_code=400,
            expected_error_message="'attachments[0]' is invalid: 'key' must be a string."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments=[{'key': 'key1'}],
            expected_status_code=400,
            expected_error_message="'attachments[0]' is invalid: Missing 'value'."
        )

        self.__send_work_message(
            token,
            message="Hello",
            raw_attachments=[{'key': 'key1', 'value': 100}],
            expected_status_code=400,
            expected_error_message="'attachments[0]' is invalid: 'value' must be a string."
        )

    def test_send_message(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.set_presence_status(
            token,
            status_id=ONLINE_ID
        )
        self.__accept_work(token)

        message_id = uuid()
        mock = self.__send_work_message(token, "Hello", message_id=message_id)
        req = mock.pop_request()
        body = json.loads(req.body)
        self.assertEqual('lmagent', body['channelType'])
        self.assertEqual(DEFAULT_WORK_TARGET_ID, body['workId'])
        self.assertEqual("Hello", body['text'])
        self.assertHasLength(0, body['attachments'])
        self.assertEqual('HUMAN_AGENT', body['intent'])
        self.assertEqual(message_id, body['messageId'])
        self.assertEqual("text/plain;charset=UTF-8", req.get_header('Content-Type'))
        self.assertEqual("*/*", req.get_header('Accept'))
        print(json.dumps(req.headers, indent=True))

        message_id = uuid()
        mock = self.__send_work_message(
            token,
            message="Hello",
            attachments={'key': 'value', 'key2': 'value2'},
            message_id=message_id)
        req = mock.pop_request()
        body = json.loads(req.body)
        # According to Dart code, you cannot send both text and attachments
        self.assertIsNone(body.get('text'))
        self.assertEqual([{'key': 'value'}, {'key2': 'value2'}], body['attachments'])

    def test_decline_work(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.set_presence_status(token, ONLINE_ID)

        self.__decline_work(
            token,
            "bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workId' is invalid: value 'bad' is malformed - regex='^0Bz[a-zA-Z0-9]{12,15}'."
        )

        self.__decline_work(
            token,
            decline_reason='v' * (MAX_DECLINE_REASON_LENGTH + 1),
            expected_status_code=400
        )

        self.__decline_work(token)
        events = self.query_events_by_token(token, EventType.WORK_DECLINED)
        self.assertHasLength(1, events)
        event = events[0]
        self.assertEqual(DEFAULT_WORK_ID, event.get_event_key('workId'))
        self.assertIsNone(event.get_event_key('declineReason'))

        self.__decline_work(token, decline_reason="My own reasons.")
        events = self.query_events_by_token(token, EventType.WORK_DECLINED)
        self.assertHasLength(2, events)
        event = events[1]
        self.assertEqual(DEFAULT_WORK_ID, event.get_event_key('workId'))
        self.assertEqual("My own reasons.", event.get_event_key('declineReason'))

    def test_close_work(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.set_presence_status(token, ONLINE_ID)
        self.__accept_work(token)

        self.__close_work(
            token,
            "bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workTargetId' is invalid: value 'bad' has invalid length of 3, must be 15 or 18."
        )
        self.__close_work(token)
        events = self.query_events_by_token(token, EventType.WORK_CLOSED)
        self.assertHasLength(1, events)
        event = events[0]
        self.assertEqual(DEFAULT_WORK_ID, event.get_event_key('workId'))

    def setUp(self) -> None:
        super().setUp()
        self.sequence_counter = 0

    def setup_mock_response(self, url: str, status_code: int = 200, body: Any = None,
                            mock: Optional[ExtendedHttpMockSession] = None):
        mock = self.add_new_http_mock() if mock is None else mock
        mock.add_post_response(
            url,
            status_code=status_code,
            body=body,
            request_callback=self.__verify_status
        )
        return mock

    def __prep_status_call(self, status_id: str):
        mock = self.add_new_http_mock()
        end = "PresenceLogin" if status_id != OFFLINE_ID else "PresenceLogout"
        mock.add_post_response(
            f'https://somewhere-chat.lightning.force.com/chat/rest/Presence/{end}',
            200, request_callback=self.verify_presence_status)

    def verify_presence_status(self, req: HttpRequest):
        self.__verify_status(req)
        body = json.loads(req.body)
        self.body_captured = body
        status_id = body['statusId']
        if status_id != ONLINE_ID and status_id != BUSY_ID and status_id != OFFLINE_ID:
            return MockedResponse(400, body="Invalid status id")
        return None

    def __verify_status(self, req: HttpRequest):
        self.sequence_counter += 1
        seq = req.get_header("X-Liveagent-Sequence")
        self.assertIsNotNone(seq)
        self.assertEqual(self.sequence_counter, int(seq))

    def __send_work_message(self,
                            session_token: str,
                            message: Optional[str] = None,
                            work_target_id: Optional[str] = DEFAULT_WORK_TARGET_ID,
                            message_id: Optional[str] = None,
                            attachments: Dict[str, str] = None,
                            raw_attachments: Any = None,
                            expected_status_code: int = 204,
                            expected_error_message: str = None,
                            expected_error_code: str = None,
                            expected_message: str = None
                            ):
        headers = {
            'x-1440-session-token': session_token
        }
        path = f"work-conversations/{work_target_id}/messages"
        if message_id is None:
            message_id = uuid()
        elif len(message_id) == 0:
            message_id = None

        if expected_status_code == 204:
            mock = self.setup_mock_response(
                CONVERSATION_MESSAGE_URL,
                status_code=200,
                body="Some data"
            )
        else:
            mock = None

        body = {
            'id': message_id
        }

        if message is not None:
            body['messageBody'] = message

        if attachments is not None:
            att = []
            body['attachments'] = att
            for key, value in attachments.items():
                att.append({'key': key, 'value': value})
        elif raw_attachments is not None:
            body['attachments'] = raw_attachments

        self.post(
            path,
            headers=headers,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
        return mock

    def __accept_work(self,
                      session_token: str,
                      work_id: Optional[str] = DEFAULT_WORK_ID,
                      work_target_id: Optional[str] = DEFAULT_WORK_TARGET_ID,
                      expected_status_code: int = 204,
                      expected_error_message: str = None,
                      expected_error_code: str = None,
                      expected_message: str = None
                      ) -> Optional[MockHttpSession]:
        headers = {
            'x-1440-session-token': session_token
        }
        if expected_status_code == 204:
            mock = self.setup_mock_response(
                ACCEPT_WORK_URL,
                status_code=200,
                body="Some data"
            )
        else:
            mock = None
        self.post(
            "presence/actions/accept-work",
            headers=headers,
            body={
                'workId': work_id,
                'workTargetId': work_target_id
            },
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
        return mock

    def __decline_work(self,
                       session_token: str,
                       work_id: Optional[str] = DEFAULT_WORK_ID,
                       work_target_id: Optional[str] = DEFAULT_WORK_TARGET_ID,
                       decline_reason: Optional[str] = None,
                       expected_status_code: int = 204,
                       expected_error_message: str = None,
                       expected_error_code: str = None,
                       expected_message: str = None
                       ) -> Optional[MockHttpSession]:
        headers = {
            'x-1440-session-token': session_token
        }
        if expected_status_code == 204:
            mock = self.setup_mock_response(
                url=DECLINE_WORK_URL,
                status_code=200,
                body="some data"
            )
        else:
            mock = None
        body = {
            'workId': work_id,
            'workTargetId': work_target_id
        }
        if decline_reason is not None:
            body['declineReason'] = decline_reason

        self.post(
            "presence/actions/decline-work",
            headers=headers,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
        return mock

    def __close_work(self,
                     session_token: str,
                     work_target_id: Optional[str] = DEFAULT_WORK_TARGET_ID,
                     expected_status_code: int = 204,
                     expected_error_message: str = None,
                     expected_error_code: str = None,
                     expected_message: str = None
                     ) -> Optional[MockHttpSession]:
        headers = {
            'x-1440-session-token': session_token
        }
        if expected_status_code == 204:
            if not work_target_id.startswith("a17"):
                mock = self.setup_mock_response(
                    CONVERSATION_END_URL,
                    200,
                    body="some data"
                )
                self.setup_mock_response(
                    AFTER_CLOSE_WORK_URL,
                    200,
                    body="some data",
                    mock=mock
                )
            else:
                mock = self.add_new_http_mock()

            self.setup_mock_response(
                url=CLOSE_WORK_URL,
                status_code=200,
                body="some data",
                mock=mock
            )
        else:
            mock = None
        body = {'workTargetId': work_target_id}

        self.post(
            "presence/actions/close-work",
            headers=headers,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
        return mock

    def set_presence_status(self,
                            session_token: str = None,
                            status_id: str = None,
                            raw_body: str = None,
                            expected_status_code: int = 204,
                            expected_error_message: str = None,
                            expected_error_code: str = None,
                            expected_message: str = None
                            ):
        if expected_status_code == 204:
            self.__prep_status_call(status_id)
        headers = {
            'x-1440-session-token': session_token
        }
        body = {'id': status_id} if raw_body is None else raw_body

        self.post(
            "presence/actions/set-status",
            headers=headers,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
