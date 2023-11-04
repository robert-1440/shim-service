import json

from base_test import BaseTest, AsyncMode
from mocks.http_session_mock import MockedResponse
from support.live_agent_helper import ONLINE_ID, BUSY_ID, OFFLINE_ID
from utils.http_client import HttpRequest


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
        pass
