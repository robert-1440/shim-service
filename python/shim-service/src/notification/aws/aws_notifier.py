from typing import List, Optional

from aws import is_not_found_exception
from aws.sns import Sns, Subscription as SnsSubscription
from lambda_web_framework.web_exceptions import EntityExistsException
from notification import SubscriptionStatus, Subscription, Notifier
from utils import loghelper, exception_utils

logger = loghelper.get_logger(__name__)


class AwsNotifier(Notifier):
    def __init__(self, sns: Sns, topic_arn: str):
        self.sns = sns
        self.topic_arn = topic_arn

    def notify(self, subject: str, message: str):
        try:
            self.sns.publish(self.topic_arn, subject, message)
        except Exception as ex:
            logger.error(f"Failed to send message '{message}' to topic {self.topic_arn}: {exception_utils.dump_ex()}")

    def subscribe(self, subscription: Subscription):
        lwr = subscription.email_address.lower()
        for _ in filter(lambda sub: sub.endpoint.lower() == lwr, self.sns.list_subscriptions(self.topic_arn)):
            raise EntityExistsException(f"{subscription.email_address} is already subscribed.")
        self.sns.subscribe(self.topic_arn, "email", subscription.email_address)

    def unsubscribe(self, subscription: Subscription):
        assert subscription.external_id is not None
        try:
            self.sns.unsubscribe(subscription.external_id)
            return True
        except Exception as ex:
            if is_not_found_exception(ex):
                return False
            raise ex

    def list_subscriptions(self) -> List[Subscription]:
        return list(
            map(self.__to_sub,
                filter(lambda sub: sub.protocol == 'email', self.sns.list_subscriptions(self.topic_arn))))

    def find_subscription(self, email_address: str) -> Optional[Subscription]:
        lwr = email_address.lower()
        for sub in map(self.__to_sub,
                       filter(lambda sub: sub.protocol == 'email' and sub.endpoint.lower() == lwr,
                              self.sns.list_subscriptions(self.topic_arn))):
            return sub
        return None

    def __to_sub(self, source: SnsSubscription) -> Subscription:
        atts = self.sns.get_subscription_attributes(source)
        pc = atts.get('PendingConfirmation', 'false')
        status = SubscriptionStatus.PENDING if pc == 'true' else SubscriptionStatus.CONFIRMED
        return Subscription(source.endpoint, source.arn, status)
