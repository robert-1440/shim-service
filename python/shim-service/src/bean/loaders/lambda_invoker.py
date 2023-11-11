from aws import AwsClient
from bean import BeanName, Bean
from bean.beans import inject
from lambda_pkg.aws.aws_lambda_invoker import AwsLambdaInvoker


@inject(bean_instances=BeanName.LAMBDA_CLIENT,
        beans=BeanName.SQS)
def init(client: AwsClient, sqs_client_bean: Bean):
    return AwsLambdaInvoker(client, sqs_client_bean.create_supplier())
