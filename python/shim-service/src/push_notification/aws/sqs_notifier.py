import json
from typing import Dict, Optional

from aws import AwsClient
from push_notification import PushNotifier


class AwsSqsPushNotifier(PushNotifier):
    """
    This should only be available in a test instance of the shim service.  The SQS_PUSH_NOTIFICATION_QUEUE_URL environment
    variable must be set.
    """

    def __init__(self, client: AwsClient, queue_url: str):
        self.client = client
        self.queue_url = queue_url

    def _notify(self, token: str, data: Dict[str, str], dry_run: bool = False):
        if token.startswith("sqs::"):
            subject = token[5::]
            if len(subject) > 0:
                if dry_run:
                    return
                message = json.dumps(data)
                self.client.send_message(
                    QueueUrl=self.queue_url,
                    MessageBody=message,
                    MessageGroupId=subject
                )
                return
        raise Exception("Invalid token")

    @classmethod
    def get_token_prefix(cls) -> Optional[str]:
        return "sqs"
