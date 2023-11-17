from copy import copy
from typing import Optional, List

import bean
from auth import Credentials
from base_test import BaseTest, DEFAULT_TENANT_ID, create_credentials, GOOD_CREDS, DEFAULT_INSTANCE_URL, \
    DEFAULT_ACCESS_TOKEN, next_session_id
from bean import BeanName
from botomocks.lambda_mock import Invocation
from config import DEFAULT_MAX_SESSION_RETRIES
from lambda_web_framework.web_exceptions import NotAuthorizedException, ForbiddenException, GoneException, \
    ConflictException, LambdaHttpException
from mocks.gcp.firebase_admin import messaging
from pending_event import PendingEventType
from platform_channels import OMNI_PLATFORM, X1440_PLATFORM
from push_notification import PushNotificationContextSettings
from repos.aws.aws_session_contexts import AwsSessionContextsRepo
from repos.aws.aws_user_sessions import AwsUserSessionsRepo
from repos.pending_event_repo import PendingEventsRepo
from repos.session_contexts import SessionContextsRepo
from repos.sessions_repo import UserSessionExistsException
from services.sfdc.live_agent import LiveAgentWebSettings, LiveAgentPollerSettings
from services.sfdc.sfdc_session import load_with_context
from session import manager, Session, SessionStatus, ContextType, SessionContext
from session.exceptions import SessionNotActiveException
from session.token import SessionToken
from support import verification_utils
from support.credentials import TestCredentials
from utils import collection_utils
from utils.date_utils import get_system_time_in_millis, get_system_time_in_seconds, EpochSeconds

TENANT_ID = DEFAULT_TENANT_ID
SESSION_ID = "some-session-id"
USER_ID = "some-user-id"
FCM_DEVICE_TOKEN = "some-token"

_SESSION_ID_COUNTER = 0


class FakeLambdaRequest:
    def __init__(self, token: str = None,
                 creds: Optional[Credentials] = None):
        self.token = token
        self.session: Optional[Session] = None
        self.creds = creds

    def get_header(self, name: str):
        if name == 'x-1440-session-token':
            return self.token
        raise AssertionError(f"Wrong name: {name}")

    def get_required_header(self, name: str):
        return self.get_header(name)

    def set_session(self, session: Session):
        self.session = session

    def get_credentials(self):
        assert self.creds is not None
        return self.creds


def create_session(session: Session, async_connect: bool = True):
    return manager.create_session(session, async_connect)


class SessionManagerTest(BaseTest):
    user_sessions_repo: AwsUserSessionsRepo

    def test_create(self):
        sess = self.create_session(async_conn=False)
        # Make sure it verified the fcm token
        verification_utils.verify_dry_run(messaging.pop_invocation())

        repo: AwsSessionContextsRepo = bean.get_bean_instance(BeanName.SESSION_CONTEXTS_REPO)
        ctx = repo.find_session_context(sess, ContextType.WEB)
        self.assertIsNotNone(ctx)
        self.validate_expiration(ctx)
        settings = LiveAgentWebSettings.deserialize(ctx.session_data)
        self.assertEqual(1, settings.sequence)

        ctx = repo.find_session_context(sess, ContextType.LIVE_AGENT)
        self.validate_expiration(ctx)
        poller_settings = LiveAgentPollerSettings.deserialize(ctx.session_data)
        self.assertEqual(-1, poller_settings.ack)
        self.assertEqual(0, poller_settings.pc)
        self.assertEmpty(poller_settings.message_list)

        ctx = repo.find_session_context(sess, ContextType.PUSH_NOTIFIER)
        self.validate_expiration(ctx)
        ns = PushNotificationContextSettings.deserialize(ctx.session_data)
        self.assertIsNone(ns.last_seq_no)

        results = repo.query(sess.tenant_id)
        # Expect this to break when we start working on x1440, should be 4
        self.assertHasLength(3, results.rows)

    def validate_expiration(self, ctx: SessionContext):
        key = {'hashKey': f"d\t{ctx.tenant_id}", 'rangeKey': f"{ctx.session_id}\t{ctx.context_type.value}"}
        item = self.dynamodb.find_item("ShimServiceVirtualRangeTable", keys=key)
        self.assertIsNotNone(item)
        self.assertGreater(item['expireTime'], get_system_time_in_seconds())

    def test_create_and_load_sfdc_session(self):
        sess = self.create_session(async_conn=False)
        sfdc_sess = load_with_context(sess, ContextType.LIVE_AGENT)
        self.assertIsNotNone(sfdc_sess)

        # Set the session status to failed and ensure we get an error
        sess.set_failed('Forced failure')
        self.sessions_repo.update_session(sess)
        self.assertRaises(SessionNotActiveException,
                          lambda: load_with_context(sess, ContextType.LIVE_AGENT))

    def test_create_failed(self):
        """
        Here we simulate creating a session async, that fails during async operations.
        """
        session = self.create_session()
        sess = self._get_session(session)

        # Ensure all is well so far
        self.assertEqual(SessionStatus.PENDING, sess.status)
        sess.status = SessionStatus.FAILED
        sess.failure_message = "This is a failure message."
        self.sessions_repo.update_session(sess)

        sess = self.sessions_repo.find_session(sess)

        # Double check
        self.assertEqual(SessionStatus.FAILED, sess.status)
        self.assertEqual("This is a failure message.", sess.failure_message)

        # Now try a keep-alive
        try:
            self.submit_keepalive(sess)
            self.fail("Nope")
        except ConflictException as ex:
            self.assertEqual('SessionInFailedState', ex.error_code)
            self.assertEqual('The session is in a failed state: This is a failure message.', ex.message)

        # Make sure we can create a new session
        new_sess = self.create_session()

        # Make sure it is a new session id
        self.assertNotEqual(sess.session_id, new_sess.session_id)

        # Attempt the start again to ensure we get the new session id back
        sess_copy = copy(new_sess)
        sess_copy.session_id = next_session_id()
        result = create_session(sess_copy)
        self.assertFalse(result.created)
        self.assertEqual(new_sess.session_id, result.session.session_id)

        # Should still be there
        sess = self.sessions_repo.find_session(sess)
        self.assertIsNotNone(sess)

        # We should be able to end it
        self.assertTrue(self.delete_session(sess))

        # Make sure!
        self.assertRaises(GoneException, lambda: self.delete_session(sess))

    def test_async_create(self):
        session = self.construct_session()
        result = create_session(session)
        self.assertTrue(result.created)

        # Try starting another session for the same user it should return the previous session id
        new_one = self.construct_session()
        result = create_session(new_one)
        self.assertFalse(result.created)
        self.assertEqual(session.session_id, result.session.session_id)

        sess = self._get_session(session)
        self.assertEqual(SessionStatus.PENDING, sess.status)

        self.__finish_session_creation(sess)

        # Make sure there is an appropriate expiration time (hidden from API)
        self.__validate_expiration_times(session)

        # Make sure appropriate pending events were created
        self.__verify_pending_events(session)

        # Ensure the child sessions are created
        user_sess = self.user_sessions_repo.find_user_session(session)
        self.assertEqual(user_sess.session_id, result.session.session_id)

        # Ensure we get the same session id back
        session.session_id = next_session_id()
        result = create_session(session)
        self.assertFalse(result.created)

        current = self._get_session(result.session)
        self.assertEqual(result.session, current)

        # Attempt again, with no changes
        session.session_id = next_session_id()
        result = create_session(session)
        self.assertEqual(current, result.session)
        self.assertFalse(result.created)

        # Should have returned the original session
        self.assertNotEqual(session.session_id, current.session_id)
        # Ensure it did no updates
        self.assertEqual(current, self._get_session(current))

        # Mess with the access token
        new_session = copy(current)
        new_session.access_token = 'new-access-token'
        new_session.session_id = next_session_id()
        result = create_session(new_session)
        self.assertFalse(result.created)
        current = self._get_session(result.session)
        self.assertEqual(3, current.state_counter)

        # Simulate the session being deleted (due to expiration by DynamoDb)
        self.assertTrue(self.sessions_repo.delete(current.tenant_id, current.session_id))

        # The user and worker session(s) should still be there
        self.assertIsNotNone(self.user_sessions_repo.find_user_session(current))

        session = self.construct_session()
        result = create_session(session)
        self.assertTrue(result.created)
        self.assertEqual(session.session_id, result.session.session_id)

    def test_async_create_failure(self):

        # Test troubles submitting the async connect
        def callback(invocation: Invocation):
            raise ValueError("My Failure")

        self.lambda_mock.set_invoke_callback(callback)
        session = self.construct_session()
        with self.assertRaises(LambdaHttpException) as cm:
            create_session(session)

        ex: LambdaHttpException = cm.exception
        self.assertEqual(502, ex.status_code)

        # Make sure it stored the message
        sess = self._get_session(session, allow_failed=True)
        self.assertEqual(SessionStatus.FAILED, sess.status)
        self.assertEqual("My Failure", sess.failure_message)

    def _get_session_expiration_time(self, session: Session):
        item = self._find_ddb_session(session)
        return item['expireTime']

    def _find_ddb_session(self, session: Session):
        return self.dynamodb.find_item("ShimServiceSession",
                                       keys={'tenantId': session.tenant_id,
                                             'sessionId': session.session_id})

    def _find_ddb_user_session(self, session: Session):
        return self.dynamodb.find_item("ShimServiceVirtualRangeTable",
                                       keys={'hashKey': f"c\t{session.tenant_id}",
                                             'rangeKey': session.user_id})

    def test_finish_clash(self):
        """
        Simulate a condition, for whatever reason, where two background processes attempt to
        finish a connection for the same session at the same time.
        """

        session = self.create_session()

        contexts_repo: SessionContextsRepo = bean.get_bean_instance(BeanName.SESSION_CONTEXTS_REPO)
        current = contexts_repo.create_session_contexts

        hit = False

        def new_create(*args, **kwargs):
            nonlocal hit
            hit = True
            current(*args, **kwargs)
            # Put it back
            contexts_repo.create_session_contexts = current
            return current(*args, **kwargs)

        contexts_repo.create_session_contexts = new_create
        self.__finish_session_creation(session)
        self.assertTrue(hit)

    def test_keepalive(self):
        session = self.create_session()
        session_copy = copy(session)

        # Try with a different user in the session token
        session2 = copy(session)
        session2.user_id = "different-user"
        self.assertRaises(NotAuthorizedException, lambda: self.submit_keepalive(session2))

        current_expiration_time = self._get_session_expiration_time(session)

        # Update the expiration seconds
        session.expiration_seconds = 10
        self.sessions_repo.update_session(session)

        # should not have changed in the db yet
        self.assertEqual(current_expiration_time, self._get_session_expiration_time(session))

        # Session is still being created, so expect failure
        self.assertRaises(ConflictException, lambda: self.submit_keepalive(session))

        # Let's finish the session, so we can send the keepalive
        session = self.__finish_session_creation(session_copy)

        now = get_system_time_in_seconds()
        returned_time = self.submit_keepalive(session)
        self.__validate_expiration_times(session, from_time=now, expiration_seconds=10,
                                         expected_time=returned_time)

        # Now 'expire' it
        self.delete_session(session)
        self.assertRaises(GoneException, lambda: self.submit_keepalive(session))

        # Do another one, this time, delete the session as it goes to update it
        session = self.create_session()
        session = self.__finish_session_creation(session)
        self.sessions_repo.add_touch_hook(lambda sess: self.delete_session(session))
        self.assertRaises(GoneException, lambda: self.submit_keepalive(session))

    def test_delete(self):
        session = self.create_session()
        self.assertTrue(self.delete_session(session))
        self.assertRaises(GoneException, lambda: self.delete_session(session))

        # Let's make sure it deleted everything
        self.assertIsNone(self.sessions_repo.find_session(session))
        self.assertIsNone(self.user_sessions_repo.find_user_session(session))

    def test_create_with_user_already_logged_in(self):
        # Simulate user logged in with a different device token
        session = self.create_session()
        initial_session = self._get_session(session)
        session.fcm_device_token = "some-other-device"
        try:
            self.submit_session(session)
            self.fail("Should not get here")
        except UserSessionExistsException as ex:
            self.assertEqual(initial_session.session_id, ex.session_id)

        # Now, pretend the other session times out
        self.assertTrue(self.sessions_repo.delete_session(initial_session))

        self.submit_session(session)

    def test_create_with_trouble(self):
        """
        1. Create a session
        2. Create the session again with a different access token, at the same time, an update to the session happens
            (i.e. a background process is updating it for whatever reason)
        """

        session = self.create_session()
        self.assertEqual(1, session.state_counter)

        # Set up the hook to do an update when the update happens
        self.sessions_repo.add_update_hook(lambda sess: self.__inc_state_counter(sess))

        session.access_token = "new-token"
        session.session_id = next_session_id()
        current = self.submit_session(session)
        self.assertEqual("new-token", current.access_token)
        self.sessions_repo.assert_no_update_hooks()
        self.assertEqual(3, current.state_counter)

        # Do it again, but exceed the retries
        for i in range(DEFAULT_MAX_SESSION_RETRIES):
            self.sessions_repo.add_update_hook(lambda sess: self.__inc_state_counter(sess))

        session.access_token = "new-token-again"
        session.session_id = next_session_id()

        self.assertRaises(UserSessionExistsException, lambda: self.submit_session(session))
        self.sessions_repo.assert_no_update_hooks()

    def test_verify_session(self):
        creds = create_credentials("First", client_id="client-id", password="password", tenant_id=TENANT_ID)
        creds2 = create_credentials("Second", client_id="client-id", password="password", tenant_id=200)

        # First, test with missing token
        with self.assertRaises(NotAuthorizedException) as cm:
            self.__verify_session(None, creds)
        self.assertEqual(cm.exception.message, "Not Authorized: Missing X-1440-Session-Token header")

        session = self.create_session()
        token = self.__create_token(session, creds)

        # Session is being created
        self.assertRaises(ConflictException, lambda: self.__verify_session(token, creds))

        session = self.__finish_session_creation(session)
        self.assertEqual(session, self.__verify_session(token, creds))

        self.assertRaises(NotAuthorizedException, lambda: self.__verify_session(token, creds2))

        # Just one for the road - change the tenant id the creds have access to
        creds.set_tenant_id(200)
        self.assertRaises(ForbiddenException, lambda: self.__verify_session(token, creds))

    @classmethod
    def __verify_session(cls, token: Optional[str], creds: TestCredentials) -> Session:
        req = cls.__create_request(token)
        manager.verify_session(req, creds.to_credentials())
        return req.session

    @classmethod
    def __create_token(cls, session: Session, creds: TestCredentials):
        token = SessionToken(session.tenant_id, session.session_id, session.user_id)
        return token.serialize(creds.to_credentials())

    @classmethod
    def __create_request(cls, token: Optional[str]) -> FakeLambdaRequest:
        return FakeLambdaRequest(token)

    def __inc_state_counter(self, session: Session):
        session = self._get_session(session)
        self.sessions_repo.update_session(session)
        current = self._get_session(session)
        self.assertEqual(session.state_counter + 1, current.state_counter)

    def _get_session(self, session: Session, allow_failed: bool = False):
        return self.sessions_repo.get_session(
            session,
            allow_pending=True,
            allow_failure=allow_failed
        )

    def submit_session(self, session: Session) -> Session:
        session.session_id = next_session_id()
        return self._get_session(create_session(session).session)

    def create_session(self,
                       tenant_id: int = TENANT_ID,
                       creation_time: Optional[int] = None,
                       user_id: Optional[str] = None,
                       fcm_device_token: str = FCM_DEVICE_TOKEN,
                       async_conn: bool = True,
                       ) -> Session:
        session = self.construct_session(
            tenant_id=tenant_id,
            creation_time=creation_time,
            user_id=user_id,
            fcm_device_token=fcm_device_token
        )
        if not async_conn:
            self.prepare_sfdc_connection()
        sess = create_session(session, async_connect=async_conn).session
        return self._get_session(sess)

    def delete_session(self, session: Session,
                       creds: TestCredentials = GOOD_CREDS):
        token = self.__create_token(session, creds)
        return manager.delete_session_by_token(token, FakeLambdaRequest(token, creds=creds.to_credentials()))

    def submit_keepalive(self,
                         session: Session,
                         creds: TestCredentials = GOOD_CREDS) -> Optional[int]:
        token = self.__create_token(session, creds)
        return manager.keepalive(token, FakeLambdaRequest(creds=creds.to_credentials()))

    def construct_session(self,
                          tenant_id: int = TENANT_ID,
                          platform_types: List[str] = [OMNI_PLATFORM.name, X1440_PLATFORM.name],
                          creation_time: Optional[int] = None,
                          user_id: Optional[str] = None,
                          fcm_device_token: str = FCM_DEVICE_TOKEN
                          ) -> Session:

        return Session(
            tenant_id=tenant_id,
            session_id=next_session_id(),
            time_created=creation_time or get_system_time_in_millis(),
            user_id=user_id or USER_ID,
            instance_url=DEFAULT_INSTANCE_URL,
            access_token=DEFAULT_ACCESS_TOKEN,
            fcm_device_token=fcm_device_token,
            expiration_seconds=self.config.session_expiration_seconds,
            channel_platform_types=platform_types,
            update_time=get_system_time_in_millis()
        )

    def __verify_pending_events(self, session: Session):
        repo: PendingEventsRepo = bean.get_bean_instance(BeanName.PENDING_EVENTS_REPO)
        events = repo.query_events(
            PendingEventType.LIVE_AGENT_POLL,
            10, None).rows

        live_event = collection_utils.find_first_match(
            events, lambda e: e.tenant_id == session.tenant_id and e.session_id == session.session_id
        )
        if session.has_live_agent_polling():
            self.assertIsNotNone(live_event)
        else:
            self.assertIsNone(live_event)

    def __validate_expiration_times(self, session: Session,
                                    from_time: EpochSeconds = None,
                                    expiration_seconds=None,
                                    expected_time=None):
        if from_time is None:
            from_time = session.time_created // 1000
        if expiration_seconds is None:
            expiration_seconds = self.config.session_expiration_seconds
        item = self._find_ddb_session(session)
        self.assertIsNotNone(item)
        expire_time = item['expireTime']
        diff = expire_time - from_time
        if diff < expiration_seconds - 1 or diff > expiration_seconds:
            self.fail(f"Invalid expiration seconds: {diff}")

        if expected_time is not None:
            self.assertEqual(expected_time, expire_time)

        item = self._find_ddb_user_session(session)
        self.assertIsNotNone(item)
        self.assertEqual(expire_time, item['expireTime'])

    def __finish_session_creation(self, session: Session) -> Session:
        self.prepare_sfdc_connection()
        manager.finish_connection(session.tenant_id, session.session_id)
        sess = self._get_session(session)
        self.assertEqual(SessionStatus.ACTIVE, sess.status)
        return sess
