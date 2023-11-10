import json
import os

from bean import beans, BeanName
from botomocks.sqs_mock import MockSqsClient
from constants import SQS_PUSH_NOTIFICATION_QUEUE_URL
from push_notification.manager import PushNotificationManager

OUR_URL = 'https://somewhere.com/queue/MyQueue'

os.environ[SQS_PUSH_NOTIFICATION_QUEUE_URL] = OUR_URL

from base_test import BaseTest


class TestSuite(BaseTest):
    sqs_mock: MockSqsClient

    def setUp(self) -> None:
        self.sqs_mock = MockSqsClient()
        beans.override_bean(BeanName.SQS, self.sqs_mock)
        super().setUp()

    def test_sqs(self):
        logged = self.execute_and_capture_info_logs(lambda: beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_MANAGER))
        self.assertIn("Found the following notifiers: sqs.", logged)

        nm: PushNotificationManager = beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_MANAGER)
        self.assertIsNone(nm.test_push_notification("sqs::good"))
        self.assertIn("Invalid token", nm.test_push_notification("sqs::"))

        data = {'name': 'name', 'value': 'value'}

        nm.send_push_notification("sqs::hello", data)
        q = self.sqs_mock.get_queue(OUR_URL)
        message = q.pop_message("hello")
        self.assertEqual(json.dumps(data), message)
