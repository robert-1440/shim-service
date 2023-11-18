import json
from typing import Any, Optional, Collection

from bean import inject, BeanType
from lambda_web_framework import init_lambda, RequestHandler
from utils import loghelper, exception_utils
from utils.date_utils import get_system_time_in_millis

# We use this below to raise unexpected exceptions

TESTING = False

logger = loghelper.get_logger(__name__)

start_time = get_system_time_in_millis()

init_lambda(logger)

__SERVER_ERROR_RESPONSE = {'statusCode': 500, 'body': {
    'errorMessage': "Internal Server Error"
}}


def _wrap(f):
    def wrapper(*args, **kwargs):
        try:
            return f(*args, **kwargs)
        except BaseException as ex:
            if TESTING:
                raise ex
            logger.severe("Unexpected exception", ex)
            exception_utils.print_exception(ex)
        return __SERVER_ERROR_RESPONSE

    return wrapper


def _check_event(event: dict) -> Optional[dict]:
    if event.get('command') == 'ping':
        __log_elapsed_time("Saw ping request, our elapsed time is")
        return {'statusCode': 200, 'body': {'pong': start_time}}
    return None


@inject(bean_types=BeanType.REQUEST_HANDLER)
@_wrap
def __dispatch(event: dict, request_handlers: Collection[RequestHandler]):
    for h in request_handlers:
        r = h.handle(event)
        if r is not None:
            return r
    return None


def _handler(event: dict, context: Any):
    r = _check_event(event)
    if r is None:
        r = __dispatch(event)
        if r is None:
            logger.severe(f"Unrecognized request: {json.dumps(event)}")
            return __SERVER_ERROR_RESPONSE
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
