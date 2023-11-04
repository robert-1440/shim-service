from typing import Any

from base_test import BaseTest
from services.sfdc.sfdc_connection import deserialize
from services.sfdc.types.aura_context import AuraSettings
from support.preload_actions_helper import UAD, APP_CONTEXT_ID, DENSITY
from test_salesforce_utils import AURA_CONTEXT, AURA_FRAMEWORK_ID


class Suite(BaseTest):

    def test_create(self):
        conn = self.create_sfdc_connection(validate=True)
        self.assertAttributeEquals('the-org-id', conn, 'organization_id')
        casted: Any = conn
        aura: AuraSettings = casted.aura_settings
        self.assertEqual(AURA_FRAMEWORK_ID, aura.fwuid)

        self.assertEqual(UAD, aura.uad)
        self.assertEqual(APP_CONTEXT_ID, aura.app_context_id)
        self.assertEqual(DENSITY, aura.density)
        aura_context = aura.aura_context
        self.assertEqual(AURA_CONTEXT, aura_context.to_record())

    def test_serialize(self):
        conn = self.create_sfdc_connection()
        data = conn.serialize()
        conn2 = deserialize(data)
        self.assertEqual(conn, conn2)
