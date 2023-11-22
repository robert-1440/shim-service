import json
import re
from typing import Dict, Any, List, Optional, Collection

from aws.dynamodb import DynamoDbRow, DynamoDbItem, from_ddb_item
from lambda_pkg.functions import LambdaInvoker
from lambda_web_framework import InvocableBeanRequestHandler, SUCCESS_RESPONSE
from platform_channels import X1440_PLATFORM
from repos.session_contexts import SessionContextsRepo
from tenant import PendingTenantEvent, PendingTenantEventType
from tenant.repo import PendingTenantEventRepo
from utils import loghelper
from utils.exception_utils import dump_ex
from utils.threading_utils import start_thread

logger = loghelper.get_logger(__name__)

_REGEX = re.compile(r"arn:aws:dynamodb:[^:]+:[^:]+:table/([^/]+)/stream/")


def has_x1440_platform(record: DynamoDbItem):
    entry = from_ddb_item(record['dynamodb']['NewImage'])
    return X1440_PLATFORM.name in entry['platformTypes']


def _extract_table_name(arn: str) -> Optional[str]:
    match = _REGEX.search(arn)
    if match:
        return match.group(1)
    logger.info(f"Unable to extract table name from '{arn}'.")
    return None


class ReconstructedSession:
    def __init__(self, row: DynamoDbRow):
        self.tenant_id = row['tenantId']
        self.org_id = row['orgId']
        self.access_token = row['accessToken']
        self.instance_url = row['instanceUrl']


class PendingEventHandler:
    def __init__(self, tenant_event_repo: PendingTenantEventRepo,
                 lambda_invoker: LambdaInvoker,
                 new_sessions: Collection[ReconstructedSession]):
        self.tenant_event_repo = tenant_event_repo
        self.lambda_invoker = lambda_invoker
        self.new_sessions = new_sessions
        self.errors = False
        self.thread = start_thread(self.process)
        self.good_count = 0

    def process(self):
        for session in self.new_sessions:
            event = PendingTenantEvent(
                PendingTenantEventType.X1440_POLL,
                session.org_id,
                session.tenant_id,
                session.access_token,
                session.instance_url
            )
            try:
                self.tenant_event_repo.update_or_create(event)
                self.good_count += 1
            except BaseException as ex:
                logger.severe(f"Error creating pending tenant event for {session.tenant_id}: {dump_ex(ex)}")
                self.errors = True

    def join(self):
        self.thread.join(30)
        if self.good_count > 0:
            self.lambda_invoker.invoke_sfdc_pubsub_poller()
        if self.errors:
            raise RuntimeError("Error creating pending tenant events.")


class TableListenerProcessor(InvocableBeanRequestHandler):
    def __init__(self, repo: SessionContextsRepo,
                 tenant_event_repo: PendingTenantEventRepo,
                 lambda_invoker: LambdaInvoker):
        self.repo = repo
        self.tenant_event_repo = tenant_event_repo
        self.lambda_invoker = lambda_invoker

    def handle(self, event: Dict[str, Any]) -> Optional[Dict[str, Any]]:
        records = event.get('Records')
        if records is not None and type(records) is list and len(records) > 0:
            record = records[0]
            if 'dynamodb' in record:
                self.invoke(event)
                return SUCCESS_RESPONSE

        return None

    def invoke(self, parameters: Dict[str, Any]):
        records = parameters.get('Records')
        if records is None:
            return
        logger.info(f"Received event:\n{json.dumps(records, indent=2)}")
        new_sessions: Dict[str, ReconstructedSession] = {}

        def local_filter(record: Dict[str, Any]) -> bool:
            table = _extract_table_name(record['eventSourceARN'])
            if table == 'ShimServiceSession':
                event_name = record['eventName']
                if event_name == 'REMOVE':
                    return True
                if event_name == 'INSERT':
                    try:
                        if has_x1440_platform(record):
                            session = ReconstructedSession(record['dynamodb']['NewImage'])
                            new_sessions[session.tenant_id] = session
                    except BaseException as ex:
                        logger.severe(f"Failed: {dump_ex(ex)}")

            return False

        records_to_delete: List[DynamoDbRow] = list(
            map(lambda r: r['dynamodb']['Keys'], filter(local_filter, records))
        )

        if len(new_sessions) > 0:
            pe_handler = PendingEventHandler(self.tenant_event_repo, self.lambda_invoker, new_sessions.values())
        else:
            pe_handler = None

        if len(records_to_delete) > 0:
            self.repo.delete_by_row_keys(records_to_delete)

        if pe_handler is not None:
            pe_handler.join()
