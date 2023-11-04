from better_test_case import BetterTestCase
from utils.http_utils import Raw, encode_form_data


class HttpUtilsSuite(BetterTestCase):

    def test_encode_form_data(self):
        params = {
            'token': 'hello/world',
            'raw': Raw('raw%2Ffield')
        }

        encoded = encode_form_data(params)
        self.assertEqual('token=hello%2Fworld&raw=raw%2Ffield', encoded)
