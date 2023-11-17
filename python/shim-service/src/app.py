import json
from traceback import print_exc
from typing import Any, Dict, Optional

import bean
from bean import BeanName, inject
from lambda_web_framework import WebRequestProcessor, init_lambda
from lambda_web_framework.request import LambdaHttpResponse
from lambda_web_framework.web_exceptions import LambdaHttpException
from utils import loghelper
from utils.date_utils import get_system_time_in_millis

# We use this below to raise unexpected exceptions

TESTING = False

logger = loghelper.get_logger(__name__)

start_time = get_system_time_in_millis()

init_lambda(logger)

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
        bean.invoke_bean_by_name(bean_name, event.get('parameters'))
        return {'StatusCode': 200}
    except BaseException as ex:
        logger.severe("Unexpected exception", ex)
        print_exc()
        return __SERVER_ERROR_RESPONSE


def _check_event(event: dict) -> Optional[dict]:
    if event.get('command') == 'ping':
        __log_elapsed_time("Saw ping request, our elapsed time is")
        return {'statusCode': 200, 'body': {'pong': start_time}}
    records = event.get('Records')
    if records is not None and type(records) is list and len(records) > 0:
        record = records[0]
        if 'dynamodb' in record:
            new_event = {
                'bean': BeanName.TABLE_LISTENER_PROCESSOR.name,
                'parameters': dict(event)
            }
            event.clear()
            event.update(new_event)
    return None


def _handler(event: dict, context: Any):
    r = _check_event(event)
    if r is not None:
        return r
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


def __log_elapsed_time(message: str = "Total elapsed time"):
    elapsed = get_system_time_in_millis() - start_time
    logger.info(f"{message}: {elapsed / 1000:0.3f} seconds.")


def handler(event: dict, context: Any):
    try:
        result = _handler(event, context)
        __log_elapsed_time()
        return result
    except BaseException as ex:
        logger.severe("Unexpected exception", ex=ex)
        raise ex
