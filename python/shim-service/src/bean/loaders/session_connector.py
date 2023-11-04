from typing import Dict, Any

from bean import InvocableBean
from session import manager


class Invoker(InvocableBean):

    def invoke(self, parameters: Dict[str, Any]):
        manager.finish_connection(parameters['tenantId'], parameters['sessionId'])
        return None


def init():
    return Invoker()
