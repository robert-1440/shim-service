import json
from typing import Optional

from base_test import BaseTest, AsyncMode, DEFAULT_WORK_ID, DEFAULT_WORK_TARGET_ID
from mocks.http_session_mock import MockedResponse, MockHttpSession
from support.live_agent_helper import ONLINE_ID, BUSY_ID, OFFLINE_ID
from utils.http_client import HttpRequest

ACCEPT_WORK_URL = "https://somewhere-chat.lightning.force.com/chat/rest/Presence/AcceptWork"


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

        self.assertEqual(BUSY_ID, self.body_captured['statusId'])
        self.set_presence_status(
            session_token,
            status_id=OFFLINE_ID
        )
        self.assertEqual(OFFLINE_ID, self.body_captured['statusId'])

        # We called it 3 times (the first one was rejected by the service not SFDC)
        self.assertEqual(3, self.sequence_counter)

    def test_accept_work(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.accept_work(
            token,
            "bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workId' is invalid: value 'bad' is malformed - regex='^0Bz[a-zA-Z0-9]{12,15}'."
        )

        self.accept_work(
            token,
            work_target_id="bad",
            expected_status_code=400,
            expected_error_code="InvalidParameter",
            expected_error_message="'workTargetId' is invalid: value 'bad' is malformed - "
                                   "regex='^0Mw[a-zA-Z0-9]{12,15}'."
        )

        mock = self.add_new_http_mock()
        mock.add_post_response(
            ACCEPT_WORK_URL,
            status_code=400,
            body={
                'sfErrorCode': "This is an error."
            }
        )

        self.accept_work(
            token,
            expected_status_code=502,
            expected_error_message="SF call failed."
        )

    def setUp(self) -> None:
        super().setUp()
        self.sequence_counter = 0

    def __prep_status_call(self, status_id: str):
        mock = self.add_new_http_mock()
        end = "PresenceLogin" if status_id != OFFLINE_ID else "PresenceLogout"
        mock.add_post_response(
            f'https://somewhere-chat.lightning.force.com/chat/rest/Presence/{end}',
            200, request_callback=self.verify_status)

    def verify_status(self, req: HttpRequest):
        self.sequence_counter += 1
        seq = req.get_header("X-Liveagent-Sequence")
        self.assertIsNotNone(seq)
        self.assertEqual(self.sequence_counter, int(seq))

        body = json.loads(req.body)
        self.body_captured = body
        status_id = body['statusId']
        if status_id != ONLINE_ID and status_id != BUSY_ID and status_id != OFFLINE_ID:
            return MockedResponse(400, body="Invalid status id")
        return None

    def accept_work(self,
                    session_token: str,
                    work_id: Optional[str] = DEFAULT_WORK_ID,
                    work_target_id: Optional[str] = DEFAULT_WORK_TARGET_ID,
                    expected_status_code: int = 200,
                    expected_error_message: str = None,
                    expected_error_code: str = None,
                    expected_message: str = None
                    ) -> Optional[MockHttpSession]:
        headers = {
            'x-1440-session-token': session_token
        }
        if expected_status_code == 200:
            mock = self.add_new_http_mock()
            mock.add_post_response(
                url=ACCEPT_WORK_URL,
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

    def set_presence_status(self,
                            session_token: str,
                            status_id: str,
                            expected_status_code: int = 200,
                            expected_error_message: str = None,
                            expected_error_code: str = None,
                            expected_message: str = None
                            ):
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
