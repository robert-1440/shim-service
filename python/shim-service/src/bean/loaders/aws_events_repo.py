from aws.dynamodb import DynamoDb
from bean import BeanName, inject
from repos.aws.aws_events import AwsEventsRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(dynamodb: DynamoDb):
    return AwsEventsRepo(dynamodb)
