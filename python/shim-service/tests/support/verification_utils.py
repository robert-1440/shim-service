import json
from typing import Any, Dict

from mocks.gcp.firebase_admin.messaging import Invocation as PushInvocation


def assert_equal(expected: Any, actual: Any):
    if expected != actual:
        raise AssertionError(f"Expected '{expected}', got '{actual}'.")


def assert_true(condition: bool):
    if not condition:
        raise AssertionError("Expected true")


def assert_false(condition: bool):
    if condition:
        raise AssertionError("Expected true")


def assert_is_none(v: Any):
    if v:
        raise AssertionError(f"Was expecting None vs {v}")


def assert_is_not_none(v: Any):
    if not v:
        raise AssertionError(f"Was not expecting None.")


def verify_dry_run(push: PushInvocation):
    assert_true(push.dry_run)
    assert_equal({'type': 'validation'}, push.message.data)


def verify_async_result(push: PushInvocation, sequence: int = 1):
    assert_false(push.dry_run)
    data = push.data.get('x1440Payload')
    assert_is_not_none(data)
    record = json.loads(data)
    payload = __parse_x1440(push, 'AsyncResult')
    assert_equal(sequence, payload['sequence'])
    assert_true(payload['isSuccess'])


def verify_agent_chat_request(push: PushInvocation):
    payload = __parse_x1440(push, 'LmAgent/ChatRequest')
    print(json.dumps(payload, indent=True))
    messages = payload['messages']
    assert_equal(1, len(messages))
    message =messages[0]
    assert_equal('Hello?', message['content'])
    assert_equal(1, message['sequence'])


def __parse_x1440(push: PushInvocation, message_type: str) -> Dict[str, Any]:
    assert_false(push.dry_run)
    data = push.data.get('x1440Payload')
    assert_is_not_none(data)
    record = json.loads(data)
    assert_equal('omni', record['platformType'])
    assert_equal(message_type, record['messageType'])
    return json.loads(record['message'])
