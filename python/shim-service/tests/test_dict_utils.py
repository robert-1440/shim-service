from better_test_case import BetterTestCase
from utils.dict_utils import ReadOnlyDict, set_if_not_none, get_or_create


class MyObject:
    def __init__(self, a: str = None, b: str = None, c: str = None):
        self.a = a
        self.b = b
        self.c = c


class DictUtilsTest(BetterTestCase):

    def test_set_if_not_none(self):
        record = {}
        set_if_not_none(record, 'bad', None)
        set_if_not_none(record, 'good', 'value')
        self.assertHasLength(1, record)
        self.assertEqual('value', record['good'])

    def test_get_or_create(self):
        record = {}
        result = get_or_create(record, 'list', list)

        self.assertHasLength(1, record)
        self.assertSame(result, get_or_create(record, 'list', list))

    def test_read_only(self):
        source = {
            'a': 'a',
            'b': 'b'
        }

        ro = ReadOnlyDict(source)

        def set_it():
            nonlocal ro
            ro['c'] = 'c'

        def delete_it():
            nonlocal ro
            del ro['c']

        self.assertRaises(NotImplementedError, set_it)
        self.assertRaises(NotImplementedError, delete_it)
        self.assertRaises(NotImplementedError, lambda: ro.pop('c'))
        self.assertRaises(NotImplementedError, ro.popitem)
        self.assertRaises(NotImplementedError, ro.clear)
        self.assertRaises(NotImplementedError, lambda: ro.update({}))
