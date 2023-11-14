import logging
import os
from http.client import HTTPConnection
from queue import Queue

from base_test import setup_ddb
from bean import beans, BeanName
from botomocks.dynamodb_mock import MockDynamoDbClient
from botomocks.lambda_mock import MockLambdaClient
from botomocks.scheduler_mock import MockSchedulerClient
from botomocks.sm_mock import MockSecretsManagerClient
from manual.mock_push_notifications_repo import MockPushNotificationsRepo
from manual.polling_events import EventListener, PollingEvent
from mocks.admin_client_mock import MockAdminClient
from mocks.mock_push_notifier import MockPushNotifier
from repos.secrets import PushNotificationProviderCredentials
from support import secrets, thread_utils


def debug_requests_on():
    HTTPConnection.debuglevel = 1

    logging.basicConfig()
    logging.getLogger().setLevel(logging.DEBUG)
    requests_log = logging.getLogger("requests.packages.urllib3")
    requests_log.setLevel(logging.DEBUG)
    requests_log.propagate = True


os.environ['AWS_ACCESS_KEY_ID'] = "invalid"
os.environ['AWS_SECRET_ACCESS_KEY'] = "invalid"

scheduler_client = MockSchedulerClient()
beans.override_bean(BeanName.SCHEDULER_CLIENT, scheduler_client)
lambda_client = MockLambdaClient(allow_all=True)
beans.override_bean(BeanName.LAMBDA_CLIENT, lambda_client)

ddb_client = MockDynamoDbClient()
setup_ddb(ddb_client)
beans.override_bean(BeanName.DYNAMODB_CLIENT, ddb_client)
sm_client = MockSecretsManagerClient()
beans.override_bean(BeanName.SECRETS_MANAGER_CLIENT, sm_client)
secrets.install()

push_notifier_mock = MockPushNotifier()
beans.override_bean(BeanName.PUSH_NOTIFIER, push_notifier_mock)


def create_creds():
    return PushNotificationProviderCredentials({'clientId': 'clientId'})


_queue = Queue(maxsize=10)


def event_listener(event: PollingEvent):
    _queue.put(event)


class OurListener(EventListener):
    def process(self, event: PollingEvent):
        event_listener(event)


beans.override_bean(BeanName.PUSH_NOTIFICATION_CREDS, lambda: create_creds())
admin_client = MockAdminClient()
beans.override_bean(BeanName.ADMIN_CLIENT, admin_client)
mock_push_repo = MockPushNotificationsRepo(OurListener())
beans.override_bean(BeanName.PUSH_NOTIFICATION_REPO, mock_push_repo)


def init(listener: EventListener):
    def worker():
        while True:
            event = _queue.get()
            listener.process(event)

    thread_utils.start_thread(worker)
