from aws.dynamodb import DynamoDb
from bean import Bean, BeanName, inject
from config import Config
from repos.aws.aws_session_contexts import AwsSessionContextsRepo


@inject(bean_instances=(BeanName.DYNAMODB, BeanName.CONFIG),
        beans=(
                BeanName.SEQUENCE_REPO,
                BeanName.SESSIONS_REPO,
                BeanName.SFDC_SESSIONS_REPO,
                BeanName.PENDING_EVENTS_REPO
        ))
def init(ddb: DynamoDb,
         config: Config,
         sequence_repo_bean: Bean,
         sessions_repo_bean: Bean,
         sfdc_sessions_repo_bean: Bean,
         pending_events_repo_bean: Bean):
    return AwsSessionContextsRepo(
        ddb,
        sequence_repo_bean.create_supplier(),
        sessions_repo_bean.create_supplier(),
        sfdc_sessions_repo_bean.create_supplier(),
        pending_events_repo_bean.create_supplier(),
        config
    )
