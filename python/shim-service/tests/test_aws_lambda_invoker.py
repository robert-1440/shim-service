import json
import os

from base_test import BaseTest, ERROR_TOPIC_ARN
from bean import beans, BeanName
from botomocks.lambda_mock import Invocation
from lambda_pkg.aws.aws_lambda_invoker import InvocationException
from lambda_pkg.functions import LambdaFunction


class Suite(BaseTest):

    def test_invoke_from_lambda(self):
        """
        Most tests to not have AWS_LAMBDA_FUNCTION_NAME set, so we want to set it and ensure
        when calling a lambda function, it actually invokes the Scheduler function to invoke it.

        We'll also force the invocation to fail to cover that code.
        """

        invoker = beans.get_bean_instance(BeanName.LAMBDA_INVOKER)
        os.environ['AWS_LAMBDA_FUNCTION_NAME'] = 'test'
        captured = []
        try:
            def listener(inv: Invocation):
                captured.append(inv)
                return {
                    'StatusCode': 400,
                    'FunctionError': "Some error"
                }

            self.lambda_mock.set_invoke_listener(listener)
            with self.assertRaises(InvocationException) as cm:
                invoker.invoke_function(LambdaFunction.PushNotifier, {'foo': 'bar'})
            self.assertEqual(400, cm.exception.response.status_code)
            self.assertEqual("Some error", cm.exception.response.function_error)

            n = self.sns_mock.pop_notification(ERROR_TOPIC_ARN)
            self.assertContains("Error from Lambda Function test", n.subject)
            self.assertContains("Some error", n.message)
        finally:
            del os.environ['AWS_LAMBDA_FUNCTION_NAME']

        self.assertEqual(1, len(captured))
        invocation = captured[0]
        self.assertEqual('ShimServiceLambdaScheduler', invocation.function_name)
        request = json.loads(invocation.payload)
        self.assertEqual('LAMBDA_SCHEDULER_PROCESSOR', request['bean'])
        parameters = request['parameters']
        self.assertEqual('ShimServiceNotificationPublisher', parameters['targetFunction'])
        self.assertEqual('PUSH_NOTIFIER_PROCESSOR', parameters['bean'])
        self.assertEqual({'foo': 'bar'}, parameters['parameters'])
