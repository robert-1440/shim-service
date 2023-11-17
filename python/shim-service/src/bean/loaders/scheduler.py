from aws import AwsClient
from bean import BeanName, inject
from scheduler.aws_scheduler import AwsScheduler


@inject(bean_instances=(BeanName.SCHEDULER_CLIENT, BeanName.LAMBDA_CLIENT))
def init(client: AwsClient, lambda_client: AwsClient):
    return AwsScheduler(client, lambda_client)
