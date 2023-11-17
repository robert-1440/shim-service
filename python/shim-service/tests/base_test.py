from botomocks.scheduler_mock import MockSchedulerClient

SQS_LIVE_AGENT_QUEUE_URL_ENV_NAME = "SQS_SHIMSERVICELIVEAGENTPOLLER_QUEUE_URL"
SQS_LIVE_AGENT_QUEUE_URL = "https://somewhere.1440.io/live-agent-poller-queue"
import os

os.environ[SQS_LIVE_AGENT_QUEUE_URL_ENV_NAME] = SQS_LIVE_AGENT_QUEUE_URL

import json
from enum import Enum
from io import StringIO
from typing import Dict, Any, Optional, Union, Tuple, List, Callable

import app
import bean
bean.set_resettable(True)
from botomocks.sqs_mock import MockSqsClient
from lambda_pkg.functions import LambdaFunction


# Protect us from accidentally hitting an actual AWS account
os.environ['AWS_ACCESS_KEY_ID'] = "invalid"
os.environ['AWS_SECRET_ACCESS_KEY'] = "invalid"
os.environ['ERROR_TOPIC_ARN'] = 'error:topic:arn'
os.environ['PUSH_NOTIFIER_GROUP_ROLE_ARN'] = 'push:role'
os.environ['INTERNAL_TESTING'] = "true"

SQS_NOTIFICATION_PUBLISHER_ENV_NAME = "SQS_SHIMSERVICENOTIFICATIONPUBLISHER_QUEUE_URL"
SQS_NOTIFICATION_PUBLISHER_QUEUE_URL = "https://somewhere.1440.io/notification-publisher-queue"
os.environ[SQS_NOTIFICATION_PUBLISHER_ENV_NAME] = SQS_NOTIFICATION_PUBLISHER_QUEUE_URL

import bean.beans
from auth import Credentials
from aws.dynamodb import DynamoDb
from bean import BeanName, beans, get_bean_instance
from bean.loaders import sessions_repo
from better_test_case import BetterTestCase
from botomocks.dynamodb_mock import MockDynamoDbClient
from botomocks.lambda_mock import MockLambdaClient
from botomocks.sns_mock import MockSnsClient
from config import Config
from events import EventType, Event
from instance import Instance
from mocks.extended_http_session_mock import ExtendedHttpMockSession
from mocks.gcp import install_gcp_cert
from mocks.gcp.firebase_admin import messaging
from mocks.mock_session import MockSession
from mocks.session_repo_mock import MockAwsSessionsRepo
from repos.events import EventsRepo
from services.sfdc import create_authenticator, sfdc_session
from services.sfdc.sfdc_connection import create_new_connection, SfdcConnection
from session import Session, SessionKey
from session.token import SessionToken
from support import secrets
from support.credentials import TestCredentials
from support.live_agent_helper import prepare_live_agent
from support.preload_actions_helper import prepare_preload_actions
from test_salesforce_utils import LINK, AURA_TOKEN_COOKIE_NAME, AURA_TOKEN_COOKIE_VALUE
from utils import string_utils, loghelper
from utils.date_utils import get_system_time_in_millis
from utils.dict_utils import set_if_not_none
from utils.http_client import create_client, HttpClient

app.TESTING = True
sfdc_session.TESTING = True

ROOT = "/shim-service/"

_SESSION_ID_COUNTER = 0


class AsyncMode(Enum):
    NONE = 0
    ASYNC = 1
    ASYNC_WAIT = 2


def next_session_id() -> str:
    global _SESSION_ID_COUNTER
    _SESSION_ID_COUNTER += 1
    return f"sess-{_SESSION_ID_COUNTER}"


def generate_org_id(tenant_id: int) -> str:
    org_id = f"org-id-"
    need = 15 - len(org_id)
    return org_id + str(tenant_id).rjust(need, '0')


def create_credentials(name: str, client_id: str, password: str, tenant_id: int = None) -> TestCredentials:
    return TestCredentials(name, client_id, password, None, [tenant_id] if tenant_id else None)


def configure_lambdas(lambda_list: Optional[List[LambdaFunction]]) -> MockLambdaClient:
    enabled = lambda_list is not None and len(lambda_list) > 0
    client = MockLambdaClient(allow_all=not enabled)
    beans.override_bean(BeanName.LAMBDA_CLIENT, client)
    if enabled:
        for lf in lambda_list:
            client.add_function(lf.value.name, app.handler)

        def capture(event, context):
            pass

        for lf in LambdaFunction:
            if lf not in lambda_list:
                client.add_function(lf.value.name, capture)

    return client


DEFAULT_USER_ID = "005Hs00000AIDN5IAP"
SECOND_USER_ID = "005Hs00000AIDN5IAQ"
DEFAULT_INSTANCE_URL = "https://somewhere.salesforce.com"
DEFAULT_FCM_DEVICE_TOKEN = "some-device-token"
DEFAULT_ACCESS_TOKEN = "access-token"
DEFAULT_WORK_ID = "0BzHs000005aLv4"
DEFAULT_WORK_TARGET_ID = "0MwHs0000011U8O"
ANOTHER_WORK_TARGET_ID = "0MwHs0000011U8A"

DEFAULT_TENANT_ID = 12345
ALTERNATE_TENANT_ID = 99999

DEFAULT_ORGANIZATION = generate_org_id(DEFAULT_TENANT_ID)
ALTERNATE_ORGANIZATION = generate_org_id(ALTERNATE_TENANT_ID)

GOOD_CREDS = TestCredentials("Good", "good1", "good2", tenant_ids=[DEFAULT_TENANT_ID])

ALTERNATE_CREDS = TestCredentials("AlternateGood", "alt-good1", "alt-good2", tenant_ids=[ALTERNATE_TENANT_ID])

NON_EXISTENT_CREDS = TestCredentials("NotThere", "nogood1", "nogood2")


class InvokeResponse:
    status_code: int
    body: Dict[str, Any]
    raw_body: str
    error_message: Optional[str]
    code: Optional[str]
    message: Optional[str]
    headers: Dict[str, str]

    def __init__(self, resp: Dict[str, Any]):
        self.status_code = resp['statusCode']
        self.raw_body = body = resp.get('body')
        self.headers = resp.get('headers') or {}
        if isinstance(body, str):
            try:
                body = json.loads(body)
            except Exception:
                body = None
        self.body = body
        if self.status_code // 100 != 2:

            self.error_message = self.body.get('errorMessage')
            self.code = self.body.get('code')
            self.message = self.body.get('message')
        else:
            self.error_message = None
            self.code = None
            self.message = None

    def assert_result(self, status_code: int = None,
                      error_message: str = None,
                      expected_error_code: str = None,
                      expected_message: str = None):
        if status_code is not None:
            assert status_code == self.status_code, f"Expected status code of {status_code}, got {self.status_code}"
        else:
            if self.status_code // 100 != 2:
                raise AssertionError(f"Call failed: {self.status_code} - {self.body}")
        if error_message is not None:
            assert error_message == self.error_message, (f"Expected error message '{error_message}, "
                                                         f"got {self.error_message}")

        if expected_error_code is not None:
            assert expected_error_code == self.code, f"Expected error code of {expected_error_code}, got {self.code}"
        if expected_message is not None:
            assert expected_message == self.message, f"Expected message of '{expected_message}', got '{self.message}'"

    def get_header(self, name: str) -> str:
        v = self.headers.get(name)
        if v is None:
            raise AssertionError(f"Header {name} was not returned in response.")
        return v


def sign(event: Dict[str, Any], creds: TestCredentials):
    method = event['requestContext']['http']['method']
    path = event['rawPath']
    request_time = get_system_time_in_millis()

    _, signature = creds.sign(method, path, request_time, event.get('body'))
    sig_string = f"{creds.name}:{request_time}:{signature}"
    headers = event['headers']
    sig_string = string_utils.encode_to_base64string(sig_string)
    headers['authorization'] = f"1440-HMAC-SHA256-A {sig_string}"


def setup_ddb(client: MockDynamoDbClient):
    client.add_manual_table_v2("ShimServiceSession", {'tenantId': 'N'}, {'sessionId': 'S'})
    client.add_manual_table_v2("ShimServiceEvent", {'tenantId': 'N'}, {'seqNo': 'N'})
    client.add_manual_table_v2("ShimServiceVirtualTable", {'hashKey': 'S'})
    client.add_manual_table_v2("ShimServiceVirtualRangeTable", {'hashKey': 'S'},
                               {'rangeKey': 'S'})


class BaseTest(BetterTestCase):
    disable_notification_check: bool
    sqs_mock: MockSqsClient
    instance: Instance
    http_session_mock: ExtendedHttpMockSession
    config: Config
    sessions_repo: MockAwsSessionsRepo
    http_mock_session_list: Optional[ExtendedHttpMockSession]
    save_class: Any
    lambda_mock: Optional[MockLambdaClient]
    started: bool
    scheduler_mock: MockSchedulerClient

    def __init__(self, method_name: str = None):
        super().__init__(method_name)
        self.disable_notification_check = False

    @staticmethod
    def create_http_client(session: ExtendedHttpMockSession = None) -> HttpClient:
        client = create_client()
        sess = ExtendedHttpMockSession() if session is None else session
        setattr(client, '_HttpClientImpl__session', sess)
        return client

    def add_new_http_mock(self) -> ExtendedHttpMockSession:
        sess = ExtendedHttpMockSession()
        self.http_mock_session_list.append(sess)
        return sess

    @classmethod
    def lambdas_enabled(cls) -> Optional[List[LambdaFunction]]:
        return None

    def setUp(self) -> None:
        self.started = False
        beans.reset()
        self.http_session_mock = ExtendedHttpMockSession()
        secrets.install(self.http_session_mock)
        self.ddb_mock = MockDynamoDbClient()
        self.http_mock_session_list: List[ExtendedHttpMockSession] = []
        self.scheduler_mock = MockSchedulerClient()
        self.sns_mock = MockSnsClient()
        self.sqs_mock = MockSqsClient()

        install_gcp_cert(self.http_session_mock)

        def client_builder():
            if len(self.http_mock_session_list) > 0:
                return self.create_http_client(self.http_mock_session_list.pop(0))
            return self.create_http_client()

        beans.override_bean(BeanName.HTTP_CLIENT_BUILDER, lambda: client_builder)
        beans.override_bean(BeanName.HTTP_CLIENT, self.create_http_client(self.http_session_mock))
        beans.override_bean(BeanName.DYNAMODB_CLIENT, self.ddb_mock)
        beans.override_bean(BeanName.SCHEDULER_CLIENT, self.scheduler_mock)
        beans.override_bean(BeanName.SNS_CLIENT, self.sns_mock)
        beans.override_bean(BeanName.SQS_CLIENT, self.sqs_mock)

        setup_ddb(self.ddb_mock)
        self.dynamodb: DynamoDb = bean.get_bean_instance(BeanName.DYNAMODB)
        self.user_sessions_repo = bean.get_bean_instance(BeanName.USER_SESSIONS_REPO)
        self.save_class = sessions_repo.INVOKE_CLASS
        sessions_repo.INVOKE_CLASS = MockAwsSessionsRepo
        self.sessions_repo = bean.get_bean_instance(BeanName.SESSIONS_REPO)

        #        self.sessions_repo = MockAwsSessionsRepo(self.dynamodb, self.user_sessions_repo, self.worker_sessions_repo)
        #       beans.override_bean(BeanName.SESSIONS_REPO, self.sessions_repo)

        self._test_initialized()

        self.http_session_mock.add_credentials(GOOD_CREDS)
        self.http_session_mock.add_credentials(ALTERNATE_CREDS)

        self.instance = get_bean_instance(BeanName.INSTANCE)
        self.config = bean.get_bean_instance(BeanName.CONFIG)
        self.put_organization()

        self.lambda_mock = configure_lambdas(self.lambdas_enabled())
        self.started = True

    def _test_initialized(self):
        pass

    @staticmethod
    def invoke_event(event: Dict[str, Any]):
        return app.handler(event, None)

    def __construct_event(self,
                          path: str,
                          method: str,
                          in_headers: Dict[str, Any] = None,
                          body: Union[str, Dict[str, Any]] = None,
                          ) -> Dict[str, Any]:
        if type(body) is dict:
            body = json.dumps(body)
        headers = dict(in_headers) if in_headers else {}
        event = {
            "rawPath": path,
            "headers": headers,
            "requestContext": {
                "http": {
                    "method": method,
                    "sourceIp": "127.0.0.1"
                }
            },
            "body": body
        }

        return event

    def get(self,
            path: str,
            creds: TestCredentials = GOOD_CREDS,
            expected_status_code: int = 200,
            expected_error_message: str = None) -> InvokeResponse:
        return self.invoke_web_event(
            path,
            "GET",
            creds=creds,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message
        )

    def post(self,
             path: str,
             creds: TestCredentials = GOOD_CREDS,
             headers: Dict[str, Any] = None,
             body: Any = None,
             expected_status_code: int = 200,
             expected_error_message: str = None,
             expected_error_code: str = None,
             expected_message: str = None
             ) -> InvokeResponse:
        return self.invoke_web_event(
            path,
            "POST",
            in_headers=headers,
            creds=creds,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_error_code=expected_error_code,
            expected_message=expected_message
        )

    def put(self,
            path: str,
            creds: TestCredentials = GOOD_CREDS,
            headers: Dict[str, Any] = None,
            body: Any = None,
            expected_status_code: int = 200,
            expected_error_message: str = None,
            expected_error_code: str = None,
            expected_message: str = None
            ) -> InvokeResponse:
        return self.invoke_web_event(
            path,
            "PUT",
            in_headers=headers,
            creds=creds,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_error_code=expected_error_code,
            expected_message=expected_message
        )

    def delete(self,
               path: str,
               creds: TestCredentials = GOOD_CREDS,
               expected_status_code: int = 204,
               expected_error_message: str = None) -> InvokeResponse:
        return self.invoke_web_event(
            path,
            "DELETE",
            creds=creds,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message
        )

    def invoke_web_event(self,
                         path: str,
                         method: str,
                         in_headers: Dict[str, Any] = None,
                         body: Union[str, Dict[str, Any]] = None,
                         creds: TestCredentials = GOOD_CREDS,
                         expected_status_code: int = None,
                         expected_error_message: str = None,
                         expected_error_code: str = None,
                         expected_message: str = None) -> InvokeResponse:
        if path.startswith("/"):
            path = path[1::]
        path = f"{ROOT}{path}"
        event = self.__construct_event(path, method, in_headers, body)
        if creds is not None:
            sign(event, creds)

        resp_json = app.handler(event, None)
        if resp_json is None:
            resp_dict = {'statusCode': 200}
        else:
            resp_dict = resp_json
        resp = InvokeResponse(resp_dict)
        resp.assert_result(expected_status_code, expected_error_message, expected_error_code, expected_message)
        return resp

    def provision_organization(self, tenant_id: int) -> Tuple[str, TestCredentials]:
        """
        Provisions a new tenant.

        :param tenant_id: the tenant id.
        :return: tuple of org_id, Credentials.
        """
        org_id = generate_org_id(tenant_id)
        creds = TestCredentials(f"Tenant-{tenant_id}",
                                f"client-id-{tenant_id}",
                                f"pass-{tenant_id}",
                                tenant_ids=[tenant_id])
        self.http_session_mock.add_credentials(creds)
        self.http_session_mock.add_tenant(org_id, tenant_id)
        return org_id, creds

    def put_organization(self,
                         organization_id: Optional[str] = DEFAULT_ORGANIZATION,
                         tenant_id: int = DEFAULT_TENANT_ID
                         ) -> str:
        if organization_id is None:
            organization_id = generate_org_id(tenant_id)
        self.http_session_mock.add_tenant(organization_id, tenant_id)
        return organization_id

    def tearDown(self) -> None:
        if self.started:
            if not self.disable_notification_check:
                self.sns_mock.assert_no_notifications()
            else:
                self.disable_notification_check = False
        beans.reset()
        messaging.reset()
        sessions_repo.INVOKE_CLASS = self.save_class
        global _SESSION_ID_COUNTER
        _SESSION_ID_COUNTER = 0

    def create_web_session(self,
                           org_id: str = DEFAULT_ORGANIZATION,
                           user_id: Optional[str] = DEFAULT_USER_ID,
                           instance_url: str = DEFAULT_INSTANCE_URL,
                           fcm_device_token: Optional[str] = DEFAULT_FCM_DEVICE_TOKEN,
                           access_token: Optional[str] = DEFAULT_ACCESS_TOKEN,
                           channel_platform_types: Optional[Tuple] = ('omni', 'x1440'),
                           async_mode: AsyncMode = AsyncMode.ASYNC_WAIT,
                           creds: TestCredentials = GOOD_CREDS,
                           expected_status_code: int = 202,
                           expected_error_message: str = None,
                           expected_error_code: str = None,
                           expected_message: str = None,
                           return_full_response: bool = False,
                           ) -> Optional[Union[str, InvokeResponse]]:
        body = {}
        set_if_not_none(body, "instanceUrl", instance_url)
        set_if_not_none(body, "userId", user_id)
        set_if_not_none(body, "fcmDeviceToken", fcm_device_token)
        set_if_not_none(body, "accessToken", access_token)
        set_if_not_none(body, 'channelPlatformTypes', channel_platform_types)
        headers = {}
        if async_mode != AsyncMode.NONE:
            if async_mode == AsyncMode.ASYNC_WAIT:
                self.prepare_sfdc_connection()
                assert self.lambdas_enabled(), "Lambdas are not enabled"

            headers['Prefer'] = 'respond-async'
        else:
            self.prepare_sfdc_connection()
            expected_status_code = 201 if expected_status_code == 202 else expected_status_code

        resp = self.put(
            f"organizations/{org_id}/sessions",
            creds=creds,
            headers=headers,
            body=body,
            expected_status_code=expected_status_code,
            expected_error_message=expected_error_message,
            expected_error_code=expected_error_code,
            expected_message=expected_message
        )
        if not return_full_response:
            if resp.status_code // 100 == 2:
                if async_mode == AsyncMode.ASYNC_WAIT:
                    self.lambda_mock.wait_for_completion()
                return resp.body['sessionToken']

        return resp

    def get_session_from_token(self, token: str, creds: Union[TestCredentials, Credentials] = GOOD_CREDS,
                               failure_ok: bool = False) -> Session:
        if isinstance(creds, TestCredentials):
            creds = creds.to_credentials()
        t = SessionToken.deserialize(creds, token)
        return self.sessions_repo.get_session(t, allow_failure=failure_ok)

    def create_and_return_web_session(self,
                                      org_id: str = DEFAULT_ORGANIZATION,
                                      user_id: Optional[str] = DEFAULT_USER_ID,
                                      instance_url: str = DEFAULT_INSTANCE_URL,
                                      fcm_device_token: Optional[str] = DEFAULT_FCM_DEVICE_TOKEN,
                                      access_token: Optional[str] = DEFAULT_ACCESS_TOKEN,
                                      creds: TestCredentials = GOOD_CREDS
                                      ) -> Tuple[str, Session]:
        token = self.create_web_session(
            org_id=org_id,
            user_id=user_id,
            instance_url=instance_url,
            fcm_device_token=fcm_device_token,
            access_token=access_token,
            creds=creds
        )
        return token, self.get_session_from_token(token, creds=creds.to_credentials())

    @staticmethod
    def create_mock_session(
            tenant_id: int = DEFAULT_TENANT_ID,
            session_id: Optional[str] = None,
            instance_url: str = DEFAULT_INSTANCE_URL,
            user_id: str = DEFAULT_USER_ID,
            access_token: str = DEFAULT_ACCESS_TOKEN) -> Session:
        if session_id is None:
            session_id = next_session_id()
        mock_session = MockSession(
            tenant_id=tenant_id,
            session_id=session_id,
            instance_url=instance_url,
            user_id=user_id,
            access_token=access_token
        )
        casted: Any = mock_session
        return casted

    @classmethod
    def create_sfdc_authenticator(cls, session: Optional[Session] = None,
                                  session_id: str = None):
        if session is None:
            session = cls.create_mock_session(session_id=session_id)
        return create_authenticator(session)

    def __prepare_sfdc_connection(self) -> ExtendedHttpMockSession:
        http_mock = self.add_new_http_mock()

        url = f"{DEFAULT_INSTANCE_URL}/secur/frontdoor.jsp?sid={DEFAULT_ACCESS_TOKEN}"
        framework_url = "https://somewhere2.salesforce.com/getter"

        # Set up the aura token on the first response
        http_mock.add_get_response(
            url,
            301,
            headers={
                'location': framework_url
            },
            cookies={
                AURA_TOKEN_COOKIE_NAME: AURA_TOKEN_COOKIE_VALUE
            })

        # Set up the framework id and aura context
        http_mock.add_get_response(
            framework_url,
            200,
            headers={
                'link': [
                    'some-random-link',
                    LINK
                ]
            }
        )
        sid_url = "https://somewhere.lightning.force.com/getter"
        session_url = "https://somewhere.salesforce.com/visualforce/session?url=https%3A%2F%2Fsomewhere.lightning.force.com%2Fone%2Fone.app"

        http_mock.add_get_response(
            session_url,
            301,
            headers={'location': sid_url},
            cookies={'sid': 'the-session-id'}
        )

        # Session id
        oid_url = "https://oid.salesforce.com/getter"
        http_mock.add_get_response(
            sid_url,
            301,
            headers={'location': oid_url},
            cookies={'sid': 'the-session-id'}
        )

        http_mock.add_get_response(oid_url, 200,
                                   cookies={'oid': 'the-org-id'})

        return http_mock

    def prepare_sfdc_connection(self, validate: bool = False) -> ExtendedHttpMockSession:
        mock = self.__prepare_sfdc_connection()
        prepare_preload_actions(mock, validate=validate)
        prepare_live_agent(mock, validate=validate)
        return mock

    def create_sfdc_connection(self, validate: bool = False) -> SfdcConnection:
        self.prepare_sfdc_connection(validate)
        return create_new_connection(self.create_sfdc_authenticator())

    @staticmethod
    def execute_and_capture_info_logs(caller: Callable) -> str:
        capture = StringIO()

        def info(text):
            print(text, file=capture)

        loghelper.INFO_LOGGING_HOOK = info
        try:
            caller()
            return capture.getvalue()
        finally:
            loghelper.INFO_LOGGING_HOOK = None

    def query_events_by_token(self, token: str, event_type: EventType) -> List[Event]:
        sess = self.get_session_from_token(token)
        return self.query_events(sess, event_type)

    @staticmethod
    def query_events(session_key: SessionKey, event_type: EventType) -> List[Event]:
        events_repo: EventsRepo = bean.get_bean_instance(BeanName.EVENTS_REPO)
        last_seq_no = None
        events = []
        while True:
            result = events_repo.query_events(
                session_key.tenant_id,
                last_seq_no=last_seq_no
            )

            events.extend(
                filter(lambda e: json.loads(e.event_data)[
                                     'sessionId'] == session_key.session_id and e.event_type == event_type,
                       result.rows))

            if result.next_token is None:
                break
        return events
