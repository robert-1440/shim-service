import json
import os

from bean import beans, BeanName
from push_notification.manager import PushNotificationManager

OUR_ARN = 'push:topic.arn'

os.environ['SNS_PUSH_TOPIC_ARN'] = OUR_ARN

from base_test import BaseTest


class TestSuite(BaseTest):

    def test_sns(self):
        logged = self.execute_and_capture_info_logs(lambda: beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_MANAGER))
        self.assertIn("Found the following notifiers: sns.", logged)

        nm: PushNotificationManager = beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_MANAGER)
        self.assertIsNone(nm.test_push_notification("sns::good"))
        self.assertIn("Invalid token", nm.test_push_notification("sns::"))

        data = {'name': 'name', 'value': 'value'}

        nm.send_push_notification("sns::hello", data)
        pn = self.sns_mock.pop_notification(topic_arn=OUR_ARN)

        self.assertEqual(pn.subject, "hello")
        self.assertEqual(json.dumps(data), pn.message)
