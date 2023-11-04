import json
from typing import Optional

from bean import beans, BeanName
from mocks.extended_http_session_mock import ExtendedHttpMockSession
from mocks.gcp import firebase_admin


def install_gcp_cert(mock: Optional[ExtendedHttpMockSession] = None):
    if mock is not None:
        record = {
            'private_key_id': "some-key",
            "private_key": 'some-private-key'
        }
        mock.add_secret("global/GcpCertificate", json.dumps(record))

    def cert_builder(content: str):
        return {'content': content}

    beans.override_bean(BeanName.PUSH_NOTIFICATION_CERT_BUILDER, lambda: cert_builder)
    beans.override_bean(BeanName.FIREBASE_ADMIN, firebase_admin)
