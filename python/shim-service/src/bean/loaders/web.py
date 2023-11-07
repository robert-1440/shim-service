from typing import Dict, Any

from controllers import web_sessions, web_presence, web_conversations
from lambda_web_framework import WebRequestProcessor, router
from lambda_web_framework.request import LambdaHttpRequest
from utils import loghelper

__MODULES = (web_sessions, web_presence, web_conversations)

logger = loghelper.get_logger(__name__)


class WebRequestProcessorImpl(WebRequestProcessor):
    def process(self, event: Dict[str, Any]) -> Dict[str, Any]:
        request = LambdaHttpRequest(event)
        correlation_id = request.get_header('x-correlation-id')
        if correlation_id is not None:
            loghelper.set_logging_info({'correlationId': correlation_id})
        try:
            logger.info(
                "Received Request:\n"
                f"    {request.method} {request.path}\n"
                f"    Source IP: {request.source_ip}"
            )
        finally:
            if correlation_id is not None:
                loghelper.clear_logging_info()

        return router.process(request)


def init():
    return WebRequestProcessorImpl()
