from repos.session_push_notifications import SessionPushNotificationsRepo
from session import SessionContext


class MockPushNotificationsRepo(SessionPushNotificationsRepo):

    def submit(self, context: SessionContext, message_type: str, message: str):
        print("-" * 80)
        print(f"messageType: {message_type}")
        print(f"message: {message}")
        print("-" * 80)
