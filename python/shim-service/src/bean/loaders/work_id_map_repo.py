from aws.dynamodb import DynamoDb
from bean import BeanName
from bean.beans import inject
from config import Config
from repos.aws.aws_work_id_map_repo import AwsWorkIdRepo


@inject(bean_instances=(BeanName.DYNAMODB, BeanName.CONFIG))
def init(ddb: DynamoDb, config: Config):
    return AwsWorkIdRepo(ddb, config)
