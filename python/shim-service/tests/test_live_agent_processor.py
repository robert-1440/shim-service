import json
import time
from typing import List

from base_test import BaseTest, AsyncMode, SECOND_USER_ID, DEFAULT_USER_ID, SQS_LIVE_AGENT_QUEUE_URL
from bean import beans, BeanName
from config import Config
from mocks.gcp.firebase_admin import messaging
from poll.live_agent.processor import LiveAgentPollingProcessor
from repos.session_push_notifications import SessionPushNotificationsRepo
from session import SessionStatus
from support.verification_utils import verify_dry_run, verify_async_result, verify_agent_chat_request
from utils import loghelper

POLLER_FUNCTION = "ShimServiceLiveAgentPoller"

PUSH_NOTIFIER_FUNCTION = "ShimServiceNotificationPublisher"

_MESSAGE = {
    'type': 'AsyncResult',
    'message': {"sequence": 1, "isSuccess": True}
}

_CHAT_MESSAGE = {
    "type": "LmAgent/ChatRequest",
    "message": {
        "messages": [
            {
                "content": "Hello?",
                "sequence": 1,
                "timestamp": 1698796678000,
                "name": "",
                "entryType": "Text",
                "messageId": "915d5f6f-1fa6-4d36-a60f-83a88a7a0ff9",
                "messageStatusCode": "",
                "attachments": [],
                "type": "EndUser"
            }
        ],
        "workTargetId": "0MwHs0000011U8O"
    }
}

_MESSAGE_DATA = {
    "sequence": 6,
    "offset": 474445959,
    "messages": [_MESSAGE, _CHAT_MESSAGE]

}


class TestLiveAgentPollingProcessor(BaseTest):
    processor: LiveAgentPollingProcessor

    info_logs: List[str]

    def test_invoke(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)

        mock = self.add_new_http_mock()
        mock.add_get_response(
            "https://somewhere-chat.lightning.force.com/chat/rest/System/Messages?ack=-1&pc=0",
            200,
            body=_MESSAGE_DATA
        )
        self.lambda_mock.enable_function(PUSH_NOTIFIER_FUNCTION, delayed=True)

        self.processor.invoke({})

        repo: SessionPushNotificationsRepo = beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_REPO)
        sess = self.get_session_from_token(token)
        notifications = list(repo.query_notifications(sess))
        self.assertHasLength(2, notifications)
        n = notifications[0]
        self.assertEqual(3, n.seq_no)
        self.assertEqual(_MESSAGE['message'], json.loads(n.message))
        self.assertEqual(_MESSAGE['type'], n.message_type)
        self.assertEqual('omni', n.platform_channel_type)

        n = notifications[1]
        self.assertEqual(4, n.seq_no)
        self.assertEqual(_CHAT_MESSAGE['message'], json.loads(n.message))
        self.assertEqual(_CHAT_MESSAGE['type'], n.message_type)
        self.assertEqual('omni', n.platform_channel_type)

        # Now ensure the notification processor did its thing
        self.install_notification_delay()
        self.assertGreater(self.lambda_mock.wait_for_completion(PUSH_NOTIFIER_FUNCTION), 0)

        # There should be no more notifications to push
        notifications = list(repo.query_notifications(sess))
        self.assertEmpty(notifications)

        # Check the actual notifications

        # The first one was the verification of the fcm device token
        verify_dry_run(messaging.pop_invocation())

        verify_async_result(messaging.pop_invocation())
        verify_agent_chat_request(messaging.pop_invocation())

        messaging.assert_no_invocations()

        # Make sure it scheduled another invocation since it would have seen a lock
        text = self.execute_and_capture_info_logs(
            lambda: self.sqs_mock.invoke_schedules(BeanName.PUSH_NOTIFIER_PROCESSOR))

        self.assertIn("Total number notifications sent: 0.", text)

    def install_notification_delay(self):
        """
        Use this to cause delay in processing to ensure that another thread attempts to obtain a lock while
        it is still locked (prevent flapping test).
        We do this by monkeying with the query_notifications method in the notifications repo.
        """
        repo: SessionPushNotificationsRepo = beans.get_bean_instance(BeanName.PUSH_NOTIFICATION_REPO)

        save_func = repo.query_notifications

        def my_func(*args, **kwargs):
            repo.query_notifications = save_func
            time.sleep(.1)
            return save_func(*args, **kwargs)

        repo.query_notifications = my_func

    def test_invoke_empty(self):
        self.processor.invoke({})
        self.assertEqual("No sessions to poll.", self.info_logs.pop(0))

    def test_invoke_with_error(self):
        token = self.create_web_session(async_mode=AsyncMode.NONE)
        self.processor.invoke({})
        # Make sure the session is in failed state
        sess = self.get_session_from_token(token, failure_ok=True)
        self.assertEqual(SessionStatus.FAILED, sess.status)
        self.assertEqual("Polling was shutdown.", sess.failure_message)

        self.info_logs.clear()
        self.processor.invoke({})
        self.assertEqual("No sessions to poll.", self.info_logs.pop(0))

    def test_invoke_multiple(self):
        self.create_web_session(async_mode=AsyncMode.NONE)
        self.create_web_session(async_mode=AsyncMode.NONE, user_id=SECOND_USER_ID)
        self.processor.invoke({})
        self.assertIn("Starting poll for 2 session(s) ...", self.info_logs)
        # We get two errors because it's very difficult to mock the polling
        self.sns_mock.pop_notification()
        self.sns_mock.pop_notification()

    def test_limit(self):
        # We get errors because of the unexpected GET requests
        self._disable_notification_check = True

        """
        Here we create the max events allowed per session + 1
        """
        config: Config = beans.get_bean_instance(BeanName.CONFIG)
        template_user_id = DEFAULT_USER_ID[0:len(DEFAULT_USER_ID) - 1:]
        for i in range(0, config.sessions_per_live_agent_poll_processor + 1):
            c = chr(i + 65)
            user_id = template_user_id + c
            self.create_web_session(user_id=user_id, async_mode=AsyncMode.NONE)

        self.processor.invoke({})
        self.assertIn(f"Starting poll for {config.sessions_per_live_agent_poll_processor} session(s) ...",
                      self.info_logs)

        # Make sure we had two invocations
        # One because we had more than the max events to be processed
        # One done at the end of processing
        self.sqs_mock.pop_schedule(SQS_LIVE_AGENT_QUEUE_URL)
        self.sqs_mock.pop_schedule(SQS_LIVE_AGENT_QUEUE_URL)
        self.sqs_mock.assert_no_schedules(SQS_LIVE_AGENT_QUEUE_URL)


    def setUp(self) -> None:
        super().setUp()
        self.info_logs = []
        self.processor = beans.get_bean_instance(BeanName.LIVE_AGENT_PROCESSOR)
        loghelper.INFO_LOGGING_HOOK = self.info_log

    def info_log(self, message: str):
        self.info_logs.append(message)

    def tearDown(self) -> None:
        super().tearDown()
        loghelper.INFO_LOGGING_HOOK = None
