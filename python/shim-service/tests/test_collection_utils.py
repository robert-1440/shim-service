from better_test_case import BetterTestCase
from utils import collection_utils
from utils.collection_utils import BufferedList, flat_iterator


class TestSuite(BetterTestCase):

    def test_partition(self):
        input_list = [0, 1, 2, 3, 4, 5, 6, 7, 8, 9]
        split = list(collection_utils.partition(input_list, 3))
        self.assertHasLength(4, split)
        self.assertEqual([0, 1, 2], split[0])
        self.assertEqual([3, 4, 5], split[1])
        self.assertEqual([6, 7, 8], split[2])
        self.assertEqual([9], split[3])

    def test_buffered_list(self):
        received = []

        buffer = BufferedList(10, lambda x: received.extend(x))

        buffer.add(1)
        self.assertHasLength(0, received)

        buffer.add_all([2, 3, 4, 5, 6, 7, 8, 9, 10, 11])
        self.assertHasLength(10, received)
        buffer.flush()
        self.assertHasLength(11, received)

        received.clear()
        block = [i for i in range(0, 10)] * 100
        buffer.add_all(block)
        buffer.add("LAST")
        buffer.flush()

        self.assertHasLength(1001, received)

    def test_transformer_iterator(self):
        def transformer(obj: int):
            return [obj] * obj

        input_list = [1, 2, 3, 4]
        result_list = list(flat_iterator(input_list, transformer))
        self.assertEqual([1, 2, 2, 3, 3, 3, 4, 4, 4, 4], result_list)
