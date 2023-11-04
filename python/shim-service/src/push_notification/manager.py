from typing import Dict, Optional, Collection

from push_notification import PushNotifier
from utils import loghelper

logger = loghelper.get_logger(__name__)


class PushNotificationManager:
    def __init__(self, notifiers: Collection[PushNotifier]):
        assert len(notifiers) > 0, "No notifiers found."
        self.notifiers = {}
        self.default_notifier = None

        for n in notifiers:
            prefix = n.get_token_prefix()
            if prefix is None:
                assert self.default_notifier is None, "Only one default notifier is allowed"
                self.default_notifier = n
            else:
                self.notifiers[prefix] = n

        assert self.default_notifier is not None, "No default notifier found."
        if len(self.notifiers) > 0:
            logger.info(f"Found the following notifiers: {', '.join(self.notifiers.keys())}.")

    def __find_notifier(self, token: str):
        if len(self.notifiers) > 0:
            index = token.find("::")
            if index > 0:
                prefix = token[0:index:]
                n = self.notifiers.get(prefix)
                if n is not None:
                    return n
        return self.default_notifier

    def send_push_notification(self, token: str, data: Dict[str, str]):
        self.__find_notifier(token).send_push_notification(token, data)

    def test_push_notification(self, token: str) -> Optional[str]:
        return self.__find_notifier(token).test_push_notification(token)
