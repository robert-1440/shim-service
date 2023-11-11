from auth import Credentials
from better_test_case import BetterTestCase
from cs_client import ConfigServiceCredentials
from lambda_web_framework.web_exceptions import NotAuthorizedException
from session.token import SessionToken


class SessionTokenTest(BetterTestCase):

    def test_it(self):
        creds = Credentials(ConfigServiceCredentials('MyName',
                                                     {
                                                         'clientId': 'my-id',
                                                         'password': 'my-password'
                                                     }))

        token = SessionToken(100, "some-session-id", "user-id")
        serialized = token.serialize(creds)
        self.assertEqual(serialized, token.serialize(creds))

        de_serialized = SessionToken.deserialize(creds, serialized)
        self.assertEqual(token, de_serialized)

        creds = Credentials(ConfigServiceCredentials('MyName',
                                                     {
                                                         'clientId': 'my-id',
                                                         'password': 'my-password-2'
                                                     }))

        self.assertRaises(NotAuthorizedException, lambda: SessionToken.deserialize(creds, serialized))
