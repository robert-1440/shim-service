from base_test import DEFAULT_USER_ID, DEFAULT_WORK_ID
from better_test_case import BetterTestCase
from lambda_web_framework.web_exceptions import InvalidParameterException
from utils import validation_utils


class ValidationUtilsSuite(BetterTestCase):

    def test_user_id(self):
        data = {'userId': DEFAULT_USER_ID}
        self.assertEqual(DEFAULT_USER_ID, validation_utils.get_user_id(data))

        data['userId'] = 'bad'
        self.assertRaises(InvalidParameterException, lambda: validation_utils.get_user_id(data))

    def test_work_id(self):
        data = {'workId': DEFAULT_WORK_ID}
        self.assertEqual(DEFAULT_WORK_ID, validation_utils.get_work_id(data))
