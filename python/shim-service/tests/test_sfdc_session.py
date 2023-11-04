from base_test import BaseTest
from services.sfdc import SfdcAuthenticator
from services.sfdc.live_agent.live_agent import LiveAgent
from services.sfdc.sfdc_session import create_sfdc_session, deserialize, SfdcSession
from support.live_agent_helper import SCRT, STATUSES, ACTUAL_CHAT_URL, LIVE_AGENT_SESSION


class SfdcSessionTestSuite(BaseTest):

    def test_it(self):
        auth = self.create_sfdc_authenticator()
        sfdc_sess = self.create_sfdc_session(auth)
        agent: LiveAgent = getattr(sfdc_sess, "live_agent")
        self.assertEqual(SCRT, agent.scrt_info)
        self.assertEqual(STATUSES, agent.status_options)

        self.assertEqual(ACTUAL_CHAT_URL, agent.endpoint)
        self.assertEqual(LIVE_AGENT_SESSION, agent.session)

    def test_serialize(self):
        sfdc_sess = self.create_sfdc_session()
        data = sfdc_sess.serialize()
        sfdc_sess2 = deserialize(sfdc_sess, data)
        self.assertEqual(sfdc_sess, sfdc_sess2)

    def create_sfdc_session(self, authenticator: SfdcAuthenticator = None) -> SfdcSession:
        self.prepare_sfdc_connection()
        authenticator = self.create_sfdc_authenticator() if authenticator is None else authenticator
        return create_sfdc_session(authenticator)
