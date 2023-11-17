from typing import Any

from aws.dynamodb import DynamoDb
from bean import BeanName, inject


@inject(bean_instances=BeanName.DYNAMODB_CLIENT)
def init(client: Any):
    return DynamoDb(client)
