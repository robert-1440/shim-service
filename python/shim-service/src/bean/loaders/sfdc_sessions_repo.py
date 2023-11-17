from aws.dynamodb import DynamoDb
from bean import BeanName, Bean, inject
from repos.aws.abstract_repo import AbstractAwsRepo
from repos.aws.aws_sfdc_sessions_repo import AwsSfdcSessionsRepo


@inject(bean_instances=(BeanName.DYNAMODB, BeanName.SESSION_CONTEXTS_REPO), beans=BeanName.SESSIONS_REPO)
def init(dynamodb: DynamoDb, contexts_repo: AbstractAwsRepo, sessions_repo_bean: Bean):
    return AwsSfdcSessionsRepo(dynamodb, contexts_repo, sessions_repo_bean.create_supplier())
