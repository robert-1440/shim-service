import json
from typing import Dict, Optional

from aws import AwsClient
from push_notification import PushNotifier


class AwsSnsPushNotifier(PushNotifier):
    """
    This should only be available in a test instance of the shim service.  The SNS_PUSH_TOPIC_ARN environment
    variable must be set.
    """

    def __init__(self, client: AwsClient, topic_arn: str):
        self.client = client
        self.topic_arn = topic_arn

    def _notify(self, token: str, data: Dict[str, str], dry_run: bool = False):
        if token.startswith("sns::"):
            subject = token[5::]
            if len(subject) > 0:
                if dry_run:
                    return
                message = json.dumps(data)
                self.client.publish(
                    TopicArn=self.topic_arn,
                    Subject=subject,
                    Message=message
                )
                return
        raise Exception("Invalid token")

    @classmethod
    def get_token_prefix(cls) -> Optional[str]:
        return "sns"
