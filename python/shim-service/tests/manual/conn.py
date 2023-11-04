import logging
import os
from http.client import HTTPConnection

from base_test import setup_ddb
from bean import ALL_PROFILES, beans, BeanName, InvocableBean
from bean.profiles import describe_profiles
from botomocks.dynamodb_mock import MockDynamoDbClient
from botomocks.lambda_mock import MockLambdaClient
from botomocks.scheduler_mock import MockSchedulerClient
from botomocks.sm_mock import MockSecretsManagerClient
from manual.mock_push_notifications_repo import MockPushNotificationsRepo
from mocks.admin_client_mock import MockAdminClient
from mocks.mock_push_notifier import MockPushNotifier
from pending_event import PendingEventType
from platform_channels import OMNI_PLATFORM, X1440_PLATFORM
from repos.pending_event_repo import PendingEventsRepo
from repos.secrets import PushNotificationProviderCredentials
from services.sfdc import SfdcAuthenticator
from services.sfdc.live_agent import StatusOption, PresenceStatus
from services.sfdc.live_agent.omnichannel_api import load_api, OmniChannelApi
from session import Session
from session.manager import create_session, CreateResult
from support import salesforce_auth, thread_utils
from support.salesforce_auth import AuthInfo
from support.secrets import setup_mock
from utils import collection_utils
from utils.uri_utils import Uri


def debug_requests_on():
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


os.environ['AWS_ACCESS_KEY_ID'] = "invalid"
os.environ['AWS_SECRET_ACCESS_KEY'] = "invalid"
os.environ['ACTIVE_PROFILES'] = describe_profiles(ALL_PROFILES)

scheduler_client = MockSchedulerClient()
beans.override_bean(BeanName.SCHEDULER_CLIENT, scheduler_client)
lambda_client = MockLambdaClient(allow_all=True)
beans.override_bean(BeanName.LAMBDA_CLIENT, lambda_client)

ddb_client = MockDynamoDbClient()
setup_ddb(ddb_client)
beans.override_bean(BeanName.DYNAMODB_CLIENT, ddb_client)
sm_client = MockSecretsManagerClient()
beans.override_bean(BeanName.SECRETS_MANAGER_CLIENT, sm_client)
setup_mock()

push_notifier_mock = MockPushNotifier()
beans.override_bean(BeanName.PUSH_NOTIFIER, push_notifier_mock)


def create_creds():
    return PushNotificationProviderCredentials({'clientId': 'clientId'})


beans.override_bean(BeanName.PUSH_NOTIFICATION_CREDS, lambda: create_creds())
admin_client = MockAdminClient()
beans.override_bean(BeanName.ADMIN_CLIENT, admin_client)
mock_push_repo = MockPushNotificationsRepo()
beans.override_bean(BeanName.PUSH_NOTIFICATION_REPO, mock_push_repo)

pe_repo: PendingEventsRepo = beans.get_bean_instance(BeanName.PENDING_EVENTS_REPO)


def poll(session: Session):
    poller: InvocableBean = beans.get_bean_instance(BeanName.LIVE_AGENT_PROCESSOR)
    event = {}
    while True:
        events = pe_repo.query_events(PendingEventType.LIVE_AGENT_POLL, 1)
        if len(events.rows) < 1:
            break
        poller.invoke(event)


class _SfdcAuthenticatorImpl(SfdcAuthenticator):
    def __init__(self, auth_info: AuthInfo, session: Session):
        super(_SfdcAuthenticatorImpl, self).__init__(session)
        self.auth_info = auth_info

    def get_access_token(self) -> str:
        return self.auth_info.session_id


auth_info = salesforce_auth.get_auth_info()
uri = Uri.parse(auth_info.server_url).origin

session = Session(1000, 'my-session-id', None, auth_info.user_id, instance_url=uri,
                  access_token=auth_info.session_id,
                  fcm_device_token="skip::this-is-a-token", expiration_seconds=3600,
                  channel_platform_types=[OMNI_PLATFORM.name, X1440_PLATFORM.name])

result: CreateResult = create_session(session, False)
sess = result.session
t = thread_utils.start_thread(lambda: poll(sess))

t.join(3)

api: OmniChannelApi = load_api(sess)
statuses = api.get_presence_statuses()
online: PresenceStatus = collection_utils.find_first_match(statuses, lambda s: s.status_option == StatusOption.ONLINE)
assert online is not None
api.set_presence_status(online.id)

t.join()
