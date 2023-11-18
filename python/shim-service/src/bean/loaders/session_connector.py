from typing import Dict, Any

from lambda_web_framework import InvocableBeanRequestHandler
from session import manager


class Invoker(InvocableBeanRequestHandler):

    def invoke(self, parameters: Dict[str, Any]):
        manager.finish_connection(parameters['tenantId'], parameters['sessionId'])
        return None


def init():
    return Invoker()
