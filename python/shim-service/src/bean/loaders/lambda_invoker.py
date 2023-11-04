from typing import Any

from bean import BeanName
from bean.beans import inject
from lambda_pkg.aws.aws_lambda_invoker import AwsLambdaInvoker


@inject(bean_instances=BeanName.LAMBDA_CLIENT)
def init(client: Any):
    return AwsLambdaInvoker(client)
