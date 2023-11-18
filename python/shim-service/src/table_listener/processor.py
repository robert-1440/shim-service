import json
import re
from typing import Dict, Any, List, Optional

from aws.dynamodb import DynamoDbRow
from lambda_web_framework import InvocableBeanRequestHandler, SUCCESS_RESPONSE
from repos.session_contexts import SessionContextsRepo
from utils import loghelper

logger = loghelper.get_logger(__name__)

_REGEX = re.compile(r"arn:aws:dynamodb:[^:]+:[^:]+:table/([^/]+)/stream/")


def _extract_table_name(arn: str) -> Optional[str]:
    match = _REGEX.search(arn)
    if match:
        return match.group(1)
    logger.info(f"Unable to extract table name from '{arn}'.")
    return None


class TableListenerProcessor(InvocableBeanRequestHandler):
    def __init__(self, repo: SessionContextsRepo):
        self.repo = repo

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

        def local_filter(record: Dict[str, Any]) -> bool:
            table = _extract_table_name(record['eventSourceARN'])
            if table == 'ShimServiceSession':
                return record['eventName'] == 'REMOVE'
            return False

        records_to_process: List[DynamoDbRow] = list(
            map(lambda r: r['dynamodb']['Keys'], filter(local_filter, records))
        )
        if len(records_to_process) > 0:
            self.repo.delete_by_row_keys(records_to_process)
