import sys
from typing import List

from aws.dynamodb import _to_ddb_item, _from_ddb_item
from base_test import BaseTest
from support.dict_stuff import replace_properties_in_dict

RECORD_TEMPLATE = {
    "eventID": "${eventId}",
    "eventName": "REMOVE",
    "eventVersion": "1.1",
    "eventSource": "aws:dynamodb",
    "awsRegion": "us-west-1",
    "dynamodb": {
        "ApproximateCreationDateTime": 1700180973,
        "Keys": {
            "tenantId": {
                "N": "${tenantId}"
            },
            "sessionId": {
                "S": "${sessionId}"
            }
        },
        "SequenceNumber": "30864200000000007273626025",
        "SizeBytes": 57,
        "StreamViewType": "KEYS_ONLY"
    },
    "eventSourceARN": "arn:aws:dynamodb:us-west-1:433933949595:table/ShimServiceSession/stream/2023-11-16T22:14:15.335"

}


def generate_record(tenant_id: int, num: int) -> dict:
    num += 1
    props = {
        'eventId': f"event-{num}",
        'tenantId': str(tenant_id),
        'sessionId': f"session-{num}"
    }
    return replace_properties_in_dict(RECORD_TEMPLATE, props)


def build_records(tenant_id: int, num_records: int) -> List[dict]:
    return list(map(lambda n: generate_record(tenant_id, n), range(0, num_records)))


class TestSuite(BaseTest):

    def test_it(self):
        records = build_records(10001, 100)
        payload = {'Records': records}

        keys = set()

        def listener(table_name: str, key: dict):
            assert table_name == "ShimServiceVirtualRangeTable"
            entry = _from_ddb_item(key)
            value = entry['hashKey'] + "|" + entry['rangeKey']
            assert value not in keys, "Duplicate key: " + value
            keys.add(value)

        self.ddb_mock.add_delete_listener(listener)
        self.invoke_event(payload)
        # There are currently 4 context types, so we expect 100 * 4 = 400 deletes to have been issued
        self.assertHasLength(400, keys)
        self.assertEqual(400, self.ddb_mock.delete_count)
