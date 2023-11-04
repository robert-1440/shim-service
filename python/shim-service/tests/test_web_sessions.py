from copy import copy
from typing import Optional, List

from base_test import DEFAULT_ORGANIZATION, GOOD_CREDS, NON_EXISTENT_CREDS, ALTERNATE_CREDS, AsyncMode
from base_web_test import BaseWebTest
from lambda_pkg import LambdaFunction
from mocks.gcp.firebase_admin import messaging
from support.credentials import TestCredentials
from utils.date_utils import get_system_time_in_seconds


class SessionsTest(BaseWebTest):

    def test_create(self):
        session_token = self.create_web_session()
        sess = self.get_session_from_token(session_token)

        # Attempt again with the same parameters
        another = self.create_web_session(expected_status_code=200)
        self.assertEqual(session_token, another)

        # Attempt with a different device token
        resp = self.create_web_session(
            fcm_device_token="different-token",
            expected_status_code=409,
            expected_error_message="User is logged into another session.",
        )

        # Make sure it returned our session token
        self.assertEqual(session_token, resp.get_header("X-1440-Session-Token"))

    def test_create_sync_connect(self):
        self.create_web_session(async_mode=AsyncMode.NONE)

    def test_keepalive(self):
        now = get_system_time_in_seconds()
        session_token = self.create_web_session()

        # Invalid creds
        self.send_keepalive(
            session_token,
            creds=NON_EXISTENT_CREDS,
            expected_status_code=401,
            expected_error_message="Not Authorized: Unable to find 'NotThere' credentials."
        )

        # Creds that have access to the same tenant, but were not used to start the session
        creds_copy = copy(GOOD_CREDS)
        creds_copy.client_id = "different-client-id"
        self.send_keepalive(
            session_token,
            creds=creds_copy,
            expected_status_code=401,
            expected_error_message="Not Authorized: Signature mismatch."
        )

        # Cross tenant attempt
        self.send_keepalive(
            session_token,
            creds=ALTERNATE_CREDS,
            expected_status_code=403,
            expected_error_message="Forbidden: Access to organization not allowed."
        )

        result = self.send_keepalive(session_token)
        self.assertGreater(result, now)

        self.end_session(session_token)
        self.send_keepalive(
            session_token,
            expected_status_code=410,
            expected_error_message="Session is gone.")

    def test_end_session(self):
        session_token = self.create_web_session()
        self.end_session(session_token)

        self.end_session(
            session_token,
            expected_status_code=410,
            expected_error_message="Session is gone."
        )

        session_token = self.create_web_session()

        # Delete the session as it goes to delete it
        self.sessions_repo.add_delete_hook(lambda sess: self.sessions_repo.delete_session(sess))

        self.end_session(
            session_token,
            expected_status_code=410,
            expected_error_message="Session no longer exists."
        )
        self.sessions_repo.assert_no_delete_hooks()

    def test_with_bad_device_token(self):
        messaging.add_invalid_token("bad-token")
        self.create_web_session(
            expected_status_code=400,
            fcm_device_token='bad-token',
            expected_error_code='InvalidFcmDeviceToken',
            expected_message="FCM device token validation failed: Invalid token: bad-token"
        )

    def test_create_with_invalid_args(self):
        self.create_web_session(
            user_id=None,
            expected_status_code=400,
            expected_error_message="Missing parameter 'userId'."
        )

        self.create_web_session(
            user_id='not-good',
            expected_status_code=400,
            expected_error_message="Parameter value of 'not-good for parameter 'userId' "
                                   "is malformed, regex='^005[a-zA-Z0-9]{15,18}'."
        )

        self.create_web_session(
            instance_url="http://bad-one.com",
            expected_status_code=400,
            expected_error_message="instanceUrl: Only URLs with https are allowed. URL is http://bad-one.com"
        )

        self.create_web_session(
            instance_url="bad-one.com",
            expected_status_code=400,
            expected_error_message="instanceUrl: Only URLs with https are allowed. URL is bad-one.com"
        )

        self.create_web_session(
            fcm_device_token='x' * 2049,
            expected_status_code=400,
            expected_error_message="'fcmDeviceToken' is invalid: length of 2049 exceeds maximum allowed of 2048."
        )

        self.create_web_session(
            fcm_device_token=None,
            expected_status_code=400,
            expected_error_message="Missing parameter 'fcmDeviceToken'."
        )

        self.create_web_session(
            access_token='x' * 4097,
            expected_status_code=400,
            expected_error_message="'accessToken' is invalid: length of 4097 exceeds maximum allowed of 4096."
        )

        self.create_web_session(
            channel_platform_types=None,
            expected_status_code=400,
            expected_error_message="Missing parameter 'channelPlatformTypes'."
        )

        self.create_web_session(
            channel_platform_types=tuple(),
            expected_status_code=400,
            expected_error_message="Need at least one channelPlatformType."
        )

        self.create_web_session(
            channel_platform_types=('foo',),
            expected_status_code=400,
            expected_error_message="Channel type 'foo' is invalid. Must be one of omni, x1440."
        )

    def send_keepalive(self,
                       session_token: str,
                       org_id: str = DEFAULT_ORGANIZATION,
                       creds: TestCredentials = GOOD_CREDS,
                       expected_status_code: int = 200,
                       expected_error_message: str = None,
                       expected_error_code: str = None
                       ) -> Optional[int]:
        resp = self.post(
            f"organizations/{org_id}/sessions/{session_token}/actions/keep-alive",
            creds=creds,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_error_code=expected_error_code
        )
        if resp.status_code == 200:
            return resp.body['expirationTime']
        return None

    def end_session(self,
                    session_token: str,
                    org_id: str = DEFAULT_ORGANIZATION,
                    creds: TestCredentials = GOOD_CREDS,
                    expected_status_code: int = 204,
                    expected_error_message: str = None
                    ):
        self.delete(
            f"organizations/{org_id}/sessions/{session_token}",
            creds=creds,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message
        )

    def lambdas_enabled(cls) -> Optional[List[LambdaFunction]]:
        return [LambdaFunction.Web]
