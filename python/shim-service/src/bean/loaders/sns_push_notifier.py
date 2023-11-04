import os

from aws import AwsClient
from bean import BeanName
from bean.beans import inject
from push_notification.aws.sns_notifier import AwsSnsPushNotifier


@inject(bean_instances=BeanName.SNS)
def init(client: AwsClient):
    return AwsSnsPushNotifier(client, os.environ['SNS_PUSH_TOPIC_ARN'])
