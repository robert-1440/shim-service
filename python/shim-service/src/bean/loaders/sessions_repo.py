from aws.dynamodb import DynamoDb
from bean import BeanName, inject
from repos.aws.aws_events import AwsEventsRepo
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_sessions import AwsSessionsRepo
from repos.aws.aws_sfdc_sessions_repo import AwsSfdcSessionsRepo
from repos.aws.aws_user_sessions import AwsUserSessionsRepo

INVOKE_CLASS = AwsSessionsRepo


@inject(bean_instances=(BeanName.DYNAMODB,
                        BeanName.USER_SESSIONS_REPO,
                        BeanName.EVENTS_REPO,
                        BeanName.SEQUENCE_REPO,
                        BeanName.SFDC_SESSIONS_REPO))
def init(dynamodb: DynamoDb, user_sessions_repo: AwsUserSessionsRepo,
         events_repo: AwsEventsRepo,
         sequence_repo: AwsSequenceRepo,
         sfdc_sessions_repo: AwsSfdcSessionsRepo):
    return INVOKE_CLASS(
        dynamodb,
        user_sessions_repo,
        events_repo,
        sequence_repo,
        sfdc_sessions_repo
    )
