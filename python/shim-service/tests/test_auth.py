from cryptography.fernet import InvalidToken

from auth import Credentials
from better_test_case import BetterTestCase
from cs_client import ConfigServiceCredentials


class AuthTest(BetterTestCase):

    def test_obfuscation(self):
        creds = Credentials(ConfigServiceCredentials('MyName',
                                                     {
                                                         'clientId': 'my-id',
                                                         'password': 'my-password'
                                                     }))

        encrypted = creds.obfuscate_data('Hello, world!')
        decrypted = creds.clarify_data(encrypted)
        self.assertEqual('Hello, world!', decrypted)

        creds = Credentials(ConfigServiceCredentials('MyName',
                                                     {
                                                         'clientId': 'my-id-2',
                                                         'password': 'my-password'
                                                     }))

        self.assertRaises(InvalidToken, lambda: creds.clarify_data(encrypted))

        creds = Credentials(ConfigServiceCredentials('MyName2',
                                                     {
                                                         'clientId': 'my-id',
                                                         'password': 'my-password'
                                                     }))
        self.assertRaises(InvalidToken, lambda: creds.clarify_data(encrypted))

        creds = Credentials(ConfigServiceCredentials('MyName',
                                                     {
                                                         'clientId': 'my-id',
                                                         'password': 'my-password-2'
                                                     }))
        self.assertRaises(InvalidToken, lambda: creds.clarify_data(encrypted))
