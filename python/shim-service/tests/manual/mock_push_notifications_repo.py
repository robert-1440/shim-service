import json
from typing import Iterable

from manual.polling_events import EventListener, PollingEvent
from push_notification import SessionPushNotification
from repos.session_push_notifications import SessionPushNotificationsRepo
from session import SessionContext, SessionKey


class MockPushNotificationsRepo(SessionPushNotificationsRepo):

    def __init__(self, listener: EventListener):
        self.listener = listener

    def set_sent(self, record: SessionPushNotification, context: SessionContext = None) -> bool:
        pass

    def query_notifications(self, session_key: SessionKey,
                            previous_seq_no: int = None) -> Iterable[SessionPushNotification]:
        pass

    def submit(self, context: SessionContext, platform_channel_type: str, message_type: str, message: str):
        print("-" * 80)
        print(f"messageType: {message_type}")
        print(f"message: {message}")
        print("-" * 80)

        message_data = json.loads(message)
        event = PollingEvent.construct_event(message_type, message_data)
        if event is not None:
            self.listener.process(event)
