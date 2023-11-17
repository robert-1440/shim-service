from aws.dynamodb import DynamoDb
from bean import BeanName, inject
from repos.aws.aws_events import AwsEventsRepo
from repos.aws.aws_sequence import AwsSequenceRepo


@inject(bean_instances=(BeanName.DYNAMODB, BeanName.EVENTS_REPO))
def init(ddb: DynamoDb, events_repo: AwsEventsRepo):
    return AwsSequenceRepo(ddb, events_repo)
