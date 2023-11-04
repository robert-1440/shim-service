from aws.dynamodb import DynamoDb
from bean import BeanName
from bean.beans import inject
from repos.aws.aws_resource_lock import AwsResourceLockRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(ddb: DynamoDb):
    return AwsResourceLockRepo(ddb)
