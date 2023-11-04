from aws.dynamodb import DynamoDb
from bean import BeanName
from bean.beans import inject
from repos.aws.aws_events import AwsEventsRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(ddb: DynamoDb):
    return AwsEventsRepo(ddb)
