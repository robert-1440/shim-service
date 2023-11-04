from typing import Any

from aws.dynamodb import DynamoDb
from bean import BeanName
from bean.beans import inject


@inject(bean_instances=BeanName.DYNAMODB_CLIENT)
def init(client: Any):
    return DynamoDb(client)
