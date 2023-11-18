from aws.sns import Sns
from notification import Notifier
from utils import loghelper, exception_utils

logger = loghelper.get_logger(__name__)


class AwsNotifier(Notifier):
    def __init__(self, sns: Sns, topic_arn: str):
        self.sns = sns
        self.topic_arn = topic_arn

    def notify(self, subject: str, message: str):
        try:
            self.sns.publish(self.topic_arn, subject, message)
        except BaseException as ex:
            logger.error(f"Failed to send message '{message}' to topic {self.topic_arn}: {exception_utils.dump_ex(ex)}")
