from aws.dynamodb import DynamoDb
from bean import BeanName, inject
from repos.aws.aws_pending_events_repo import AwsPendingEventsRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(ddb: DynamoDb):
    return AwsPendingEventsRepo(ddb)
