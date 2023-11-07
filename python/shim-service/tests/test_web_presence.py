import json
from typing import Optional, Any

from base_test import BaseTest, AsyncMode, DEFAULT_WORK_ID, DEFAULT_WORK_TARGET_ID
from events import EventType
from mocks.extended_http_session_mock import ExtendedHttpMockSession
from mocks.http_session_mock import MockedResponse, MockHttpSession
from support.live_agent_helper import ONLINE_ID, BUSY_ID, OFFLINE_ID
from utils.http_client import HttpRequest
from utils.validation_utils import MAX_DECLINE_REASON_LENGTH

ACCEPT_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/AcceptWork"
DECLINE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/DeclineWork"
CLOSE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/CloseWork"
CONVERSATION_END_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Conversational/ConversationEnd"
AFTER_CLOSE_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/StartAfterConversationWork"


class PresenceTests(BaseTest):
    body_captured: dict
    sequence_counter: int

    def test_set_presence(self):
        session_token = self.create_web_session(async_mode=AsyncMode.NONE)

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

        self.setup_mock_response(ACCEPT_WORK_URL)

        self.__accept_work(token)
        events = self.query_events_by_token(token, EventType.WORK_ACCEPTED)
        self.assertHasLength(2, events)
        self.assertEqual(400, events[0].get_event_key('sfdcResponse'))
        event = events[1]
        self.assertEqual(200, event.get_event_key('sfdcResponse'))
        self.assertEqual(DEFAULT_WORK_ID, event.get_event_key('workId'))
        self.assertEqual(DEFAULT_WORK_TARGET_ID, event.get_event_key('workTargetId'))

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
        body = {'workId': work_id}
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
                            session_token: str,
                            status_id: str,
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
        self.post(
            "presence-statuses",
            headers=headers,
            body={'id': status_id},
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_message=expected_message,
            expected_error_code=expected_error_code
        )
