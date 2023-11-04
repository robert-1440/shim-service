from typing import Any

from bean import BeanName
from bean.beans import inject
from repos.aws.aws_secrets import AwsSecretsRepo


@inject(bean_instances=BeanName.SECRETS_MANAGER_CLIENT)
def init(client: Any):
    return AwsSecretsRepo(client)