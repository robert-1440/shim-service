from typing import Dict, Any

from lambda_web_framework import InvocableBeanRequestHandler
from tenant.repo import PendingTenantEventRepo

_MAX_COLLECT_SECONDS = 10


class PollingSession:
    def __init__(self):
        pass


class ProcessorGroup:
    def __init__(self):
        pass


class X1440PollingProcessor(InvocableBeanRequestHandler):
    def __init__(self, pending_event_repo: PendingTenantEventRepo):
        self.pending_event_repo = pending_event_repo

    def __worker(self):
        pass

    def __collect(self):
        pass

    def invoke(self, parameters: Dict[str, Any]):
        pass
