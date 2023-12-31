from aws import AwsClient
from bean import BeanName, inject
from lambda_pkg.aws.aws_lambda_invoker import AwsLambdaInvoker


@inject(bean_instances=BeanName.LAMBDA_CLIENT)
def init(client: AwsClient):
    return AwsLambdaInvoker(client)
