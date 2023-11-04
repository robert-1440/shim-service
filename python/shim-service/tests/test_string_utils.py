import binascii
from decimal import Decimal
from typing import Any
from unittest import TestCase

from utils import string_utils
from utils.string_utils import decode_base64_to_string, encode_to_base64string, encode_to_urlsafe_base64string, \
    decode_urlsafe_base64_to_string, decode_base64_to_bytes, to_json_string, compress, decompress


class Test(TestCase):
    def test_decode_base64(self):
        string = encode_to_base64string('My Value')
        self.assertTrue(string.endswith("="))
        self.assertFalse(string.endswith("=="))

        self.assertIsNone(decode_base64_to_string(None))
        self.assertEqual('My Value', decode_base64_to_string(string))

        string = encode_to_base64string('Another value')
        self.assertTrue(string.endswith("=="))
        self.assertEqual('Another value', decode_base64_to_string(string))

        self.assertIsNone(decode_base64_to_string("not good", fail_on_error=False))
        self.assertRaises(binascii.Error, lambda: decode_base64_to_string("not good"))

        self.assertEqual(b'Another value', decode_base64_to_bytes(string))

    def test_decode_urlsafe_base64_to_string(self):
        self.assertIsNone(decode_urlsafe_base64_to_string(None))

        string = encode_to_urlsafe_base64string("Another value")
        self.assertEqual("Another value", decode_urlsafe_base64_to_string(string))
        self.assertIsNone(decode_urlsafe_base64_to_string("not good", fail_on_error=False))
        self.assertRaises(binascii.Error, lambda: decode_urlsafe_base64_to_string("not good"))

    def test_to_json_string(self):
        self.convert('hello', 'hello')
        self.convert('null', None)
        self.convert('true', True)
        self.convert('false', False)
        self.convert("1", 1)
        self.convert("1", Decimal(1))
        self.convert("1.1", 1.1)

        self.assertRaises(ValueError, lambda: to_json_string(string_utils))

    def convert(self, expected: str, obj: Any):
        self.assertEqual(expected, to_json_string(obj))

    def test_compress(self):
        data = "Hello, world!"
        self.assertEqual(data, decompress(compress(data)))
        self.assertIsNone(decompress(None))
