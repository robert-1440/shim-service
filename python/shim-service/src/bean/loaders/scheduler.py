from aws import AwsClient
from bean import BeanName
from bean.beans import inject
from scheduler.aws_scheduler import AwsScheduler


@inject(bean_instances=BeanName.SQS_CLIENT)
def init(client: AwsClient):
    return AwsScheduler(client)
