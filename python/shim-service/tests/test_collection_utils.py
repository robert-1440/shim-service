from better_test_case import BetterTestCase
from utils import collection_utils


class TestSuite(BetterTestCase):

    def test_partition(self):
        input_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        split = list(collection_utils.partition(input_list, 3))
        self.assertHasLength(4, split)
        self.assertEqual([0, 1, 2], split[0])
        self.assertEqual([3, 4, 5], split[1])
        self.assertEqual([6, 7, 8], split[2])
        self.assertEqual([9], split[3])