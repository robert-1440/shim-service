import os

from better_test_case import BetterTestCase
from botomocks.lambda_mock import MockLambdaClient
from botomocks.scheduler_mock import MockSchedulerClient
from lambda_pkg.functions import LambdaFunction
from scheduler import ScheduleTargetRate
from scheduler.aws_scheduler import AwsScheduler


class TestSuite(BetterTestCase):
    scheduler: AwsScheduler
    scheduler_client: MockSchedulerClient
    lambda_client: MockLambdaClient

    def test_arn(self):
        self.assertEqual('lambda:arn:ShimServiceWeb', self.scheduler.get_arn(LambdaFunction.Web))
        os.environ['THIS_FUNCTION_ARN'] = 'arn:aws:lambda:us-west-1:9999:function:ShimServiceLambdaScheduler'
        self.assertEqual('arn:aws:lambda:us-west-1:9999:function:ShimServiceWeb',
                         self.scheduler.get_arn(LambdaFunction.Web))

    def test_schedule_rate(self):
        target = ScheduleTargetRate(15)
        os.environ['PUSH_NOTIFIER_GROUP_ROLE_ARN'] = 'role:arn'
        self.assertTrue(self.scheduler.schedule_lambda(
            "test",
            target,
            LambdaFunction.PushNotifier,
            {'test': 'me'}
        ))
        self.assertFalse(self.scheduler.schedule_lambda(
            "test",
            target,
            LambdaFunction.PushNotifier,
            {'test': 'me'}
        ))
        s = self.scheduler_client.find_schedule('test')
        self.assertIsNotNone(s)
        self.assertEqual(15, s.rate_minutes)
        self.assertTrue(self.scheduler.delete_schedule("default", "test"))
        self.assertFalse(self.scheduler.delete_schedule("default", "test"))
        self.assertIsNone(self.scheduler_client.find_schedule('test'))

    def setUp(self):
        self.scheduler_client = MockSchedulerClient()
        self.lambda_client = MockLambdaClient(True)
        self.scheduler = AwsScheduler(self.scheduler_client, self.lambda_client)

    def tearDown(self):
        os.environ.pop("THIS_FUNCTION_ARN", None)
