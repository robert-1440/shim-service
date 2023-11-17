import os

from aws.sns import Sns
from bean import BeanName, inject
from notification.aws.aws_notifier import AwsNotifier


@inject(bean_instances=BeanName.SNS)
def init(sns: Sns):
    return AwsNotifier(sns, os.environ['ERROR_TOPIC_ARN'])
