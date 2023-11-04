from typing import List

from firebase_admin.messaging import Message


class Invocation:
    def __init__(self, message: Message, dry_run):
        self.message = message
        self.dry_run = dry_run
        self.token = message.token
        self.data = message.data


captured: List[Invocation] = []

invalid_tokens = set()


def send(message: Message, dry_run=False, app=None):
    assert message.token is not None, "No token"
    if message.token in invalid_tokens:
        raise ValueError(f"Invalid token: {message.token}")

    captured.append(Invocation(message, dry_run))


def pop_invocation() -> Invocation:
    return captured.pop(0)


def add_invalid_token(token: str):
    invalid_tokens.add(token)


def assert_no_invocations():
    if len(captured) > 0:
        raise AssertionError("We captured invocations.")


def reset():
    captured.clear()
    invalid_tokens.clear()
