from aws.dynamodb import DynamoDb
from bean import BeanName
from bean.beans import inject
from lambda_pkg import LambdaInvoker
from repos.aws.aws_sequence import AwsSequenceRepo
from repos.aws.aws_session_contexts import AwsSessionContextsRepo
from repos.aws.aws_session_push_notifications import AwsPushNotificationsRepo


@inject(bean_instances=(BeanName.DYNAMODB,
                        BeanName.SEQUENCE_REPO,
                        BeanName.SESSION_CONTEXTS_REPO,
                        BeanName.LAMBDA_INVOKER))
def init(ddb: DynamoDb,
         sequence_repo: AwsSequenceRepo,
         session_contexts_repo: AwsSessionContextsRepo,
         lambda_invoker: LambdaInvoker):
    return AwsPushNotificationsRepo(ddb, sequence_repo, session_contexts_repo, lambda_invoker)
