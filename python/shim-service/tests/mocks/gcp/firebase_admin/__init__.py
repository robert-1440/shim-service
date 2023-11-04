from typing import Any

from firebase_admin.credentials import Certificate

from mocks.gcp.firebase_admin import messaging as m

messaging = m


def initialize_app(cert: Certificate):
    any_cert: Any = cert
    outer: dict = any_cert
    content: dict = outer['content']
    assert content.get('private_key_id') == "some-key"
    assert content.get('private_key') == "some-private-key"
    return {}
