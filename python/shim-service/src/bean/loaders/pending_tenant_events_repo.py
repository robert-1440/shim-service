from aws.dynamodb import DynamoDb
from bean import inject, BeanName
from tenant.repo.aws_repo import AwsPendingTenantEventRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(dynamodb: DynamoDb):
    return AwsPendingTenantEventRepo(dynamodb)

