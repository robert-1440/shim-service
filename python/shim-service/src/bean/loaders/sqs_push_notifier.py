import os

from aws import AwsClient
from bean import BeanName
from bean.beans import inject
from constants import SQS_PUSH_NOTIFICATION_QUEUE_URL
from push_notification.aws.sqs_notifier import AwsSqsPushNotifier


@inject(bean_instances=BeanName.SQS)
def init(client: AwsClient):
    return AwsSqsPushNotifier(client, os.environ[SQS_PUSH_NOTIFICATION_QUEUE_URL])
