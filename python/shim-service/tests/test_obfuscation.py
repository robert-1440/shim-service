from cryptography.fernet import InvalidToken

from better_test_case import BetterTestCase
from utils.obfuscation import DataObfuscator


class CryptTests(BetterTestCase):

    def test_encrypter(self):
        enc = DataObfuscator(
            'password',
            'some-iv',
            'salt'
        )

        clear_text = b"Hello, this is my clear text data."
        encrypted = enc.obfuscate(clear_text)

        # This is the point of the class, to ensure the encrypted data is the same
        self.assertEqual(encrypted, enc.obfuscate(clear_text))

        # Just for sanity, us a new object to decrypt
        dec = DataObfuscator(
            'password',
            'some-iv',
            'salt'
        )

        decrypted = dec.clarify(encrypted)
        self.assertEqual(clear_text, decrypted)

        dec = DataObfuscator(
            'wrong-password',
            'some-iv',
            'salt'
        )
        self.assertRaises(InvalidToken, lambda: dec.clarify(encrypted))

        dec = DataObfuscator(
            'password',
            'wrong-iv',
            'salt'
        )

        self.assertRaises(InvalidToken, lambda: dec.clarify(encrypted))

        dec = DataObfuscator(
            'password',
            'some-iv',
            'wrong-salt'
        )
        self.assertRaises(InvalidToken, lambda: dec.clarify(encrypted))
