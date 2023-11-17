from aws.dynamodb import DynamoDb
from bean import BeanName, inject
from repos.aws.aws_user_sessions import AwsUserSessionsRepo


@inject(bean_instances=BeanName.DYNAMODB)
def init(dynamodb: DynamoDb):
    return AwsUserSessionsRepo(dynamodb)
