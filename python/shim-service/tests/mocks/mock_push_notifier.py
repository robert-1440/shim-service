from typing import Dict

from push_notification import PushNotifier


class MockPushNotifier(PushNotifier):
    def _notify(self, token: str, data: Dict[str, str], dry_run: bool = False):
        pass

    def __init__(self):
        pass
