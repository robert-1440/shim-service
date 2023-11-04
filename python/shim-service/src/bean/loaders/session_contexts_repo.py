from aws.dynamodb import DynamoDb
from bean import Bean, BeanName
from bean.beans import inject
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_session_contexts import AwsSessionContextsRepo


@inject(bean_instances=(BeanName.DYNAMODB, BeanName.SEQUENCE_REPO),
        beans=(
                BeanName.SESSIONS_REPO,
                BeanName.SFDC_SESSIONS_REPO,
                BeanName.PENDING_EVENTS_REPO
        ))
def init(ddb: DynamoDb,
         sequence_repo: AwsSequenceRepo,
         sessions_repo_bean: Bean,
         sfdc_sessions_repo_bean: Bean,
         pending_events_repo_bean: Bean):
    return AwsSessionContextsRepo(
        ddb,
        sequence_repo,
        sessions_repo_bean.create_supplier(),
        sfdc_sessions_repo_bean.create_supplier(),
        pending_events_repo_bean.create_supplier()
    )
