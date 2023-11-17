from typing import Collection

from aws.dynamodb import DynamoDb
from bean import BeanName, BeanType, inject
from repos.aws.aws_events import AwsEventsRepo, EventListener


@inject(bean_instances=BeanName.DYNAMODB,
        bean_types=BeanType.EVENT_LISTENER)
def init(ddb: DynamoDb, listeners: Collection[EventListener]):
    return AwsEventsRepo(ddb, listeners)
