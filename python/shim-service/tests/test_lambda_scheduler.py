import json

from base_test import BaseTest, ERROR_TOPIC_ARN
from lambda_pkg import lambda_scheduler
from mocks.http_session_mock import SimulatedResponse, MockedResponse


class FakeRequestsModule:
    def __init__(self):
        self.response = MockedResponse(200)
        self.captured_url = None
        self.captured_args = None

    def set_response(self, response: MockedResponse):
        self.response = response
        self.captured_url = None
        self.captured_args = None

    def post(self, url: str, **kwargs):
        self.captured_url = url
        self.captured_args = kwargs
        return SimulatedResponse(self.response)


class TestSuite(BaseTest):

    def test_invoke(self):

        fake_module = FakeRequestsModule()
        save_module = lambda_scheduler.requests
        lambda_scheduler.requests = fake_module
        try:
            lambda_scheduler.invoke("test", {"foo": "bar"})

            self.assertEqual(fake_module.captured_url,
                             "https://lambda.us-west-1.amazonaws.com/2015-03-31/functions/test/invocations")
            self.assertEqual({"foo": "bar"}, json.loads(fake_module.captured_args['data']))
            print(fake_module.captured_args)

            fake_module.set_response(MockedResponse(400, body="Invalid request"))
            lambda_scheduler.invoke("test", {"foo": "bar"})
            n = self.sns_mock.pop_notification(ERROR_TOPIC_ARN)
            self.assertEqual("Failed to invoke lambda function test, code=400, response=Invalid request", n.message)
        finally:
            lambda_scheduler.requests = save_module
