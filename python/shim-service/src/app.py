import json
from traceback import print_exc
from typing import Any, Dict

from bean import BeanName, beans, Bean
from bean.beans import inject
from lambda_web_framework import WebRequestProcessor
from lambda_web_framework.request import LambdaHttpResponse
from lambda_web_framework.web_exceptions import LambdaHttpException
from utils import loghelper

# We use this below to raise unexpected exceptions

TESTING = False

logger = loghelper.get_logger(__name__)

__SERVER_ERROR_RESPONSE = {'statusCode': 500, 'body': {
    'errorMessage': "Internal Server Error"
}}


@inject(bean_instances=BeanName.WEB_ROUTER)
def __dispatch_web_request(event: dict, web_router: WebRequestProcessor):
    try:
        return web_router.process(event)
    except LambdaHttpException as ex:
        logger.error(f"Error: {ex}")
        resp_dict = ex.to_response()
    except BaseException as ex:
        if TESTING:
            raise ex
        logger.severe("Unexpected exception", ex)
        print_exc()
        resp_dict = __SERVER_ERROR_RESPONSE
    return resp_dict


def __call_bean(bean_name: str, event: Dict[str, Any]):
    try:
        beans.invoke_bean_by_name(bean_name, event.get('parameters'))
        return {'StatusCode': 200}
    except BaseException as ex:
        logger.severe("Unexpected exception", ex)
        print_exc()
        return __SERVER_ERROR_RESPONSE


@inject(beans=BeanName.SCHEDULER)
def __check_event(event: dict, scheduler_bean: Bean) -> dict:
    # Let's see if this came from SQS
    records = event.get('Records')
    if records is not None and len(records) == 1:
        record = records[0]
        if isinstance(record, dict):
            if record.get('eventSource') == 'aws:sqs':
                scheduler_bean.get_instance().process_sqs_event(record)
                body = record.get('body')
                if body is not None:
                    return json.loads(body)
    return event


def _handler(event: dict, context: Any):
    event = __check_event(event)
    bean_name = event.get('bean')
    if bean_name is not None:
        return __call_bean(bean_name, event)
    r = __dispatch_web_request(event)
    if r is not None:
        if isinstance(r, LambdaHttpResponse):
            r = r.to_dict()
        if isinstance(r, dict):
            r['isBase64Encoded'] = False
            body = r.get('body')
            if body is not None and type(body) is dict:
                r['body'] = json.dumps(body)
    return r


def handler(event: dict, context: Any):
    try:
        return _handler(event, context)
    except BaseException as ex:
        logger.severe("Unexpected exception", ex=ex)
        raise ex
