from aws.dynamodb import DynamoDb
from bean import inject, BeanName
from tenant.repo.aws_context_repo import AwsTenantContextRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(ddb: DynamoDb):
    return AwsTenantContextRepo(ddb)
