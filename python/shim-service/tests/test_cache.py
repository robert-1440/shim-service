import time

from better_test_case import BetterTestCase
from utils.cache import TTLCache


class MyTestCase(BetterTestCase):

    def test_it(self):
        cache = TTLCache(10, ttl=0.500)
        self.assertIsNone(cache.get('key'))
        self.assertEqual(0, len(cache))
        cache['key'] = "value"

        v = cache.get('key', lambda: "no!")
        self.assertEqual('value', v)

        self.assertEqual(1, len(cache))
        self.assertEqual("value", cache.get('key'))
        self.assertEqual('value', cache.pop('key'))

        for i in range(10):
            key = f"key{i}"
            cache[key] = i

        time.sleep(.600)

        for i in range(10):
            key = f"key{i}"
            self.assertIsNone(cache.get(key))

        self.assertEqual(0, len(cache))

        self.assertEqual('1', cache.get('one', lambda: '1'))

    def test_with_loader(self):
        cache = TTLCache(5, 5)
        cache['one'] = 1
        cache['two'] = 2
        self.assertEqual(3, cache.get('three', lambda: 3))
        self.assertHasLength(3, cache)

        cache['four'] = 4
        cache['five'] = 5
        self.assertHasLength(5, cache)
        cache['six'] = 6
        self.assertHasLength(5, cache)
        # 'one' should be the oldest, therefore removed
        self.assertIsNone(cache.get('one'))
        self.assertEqual(3, cache.get('three', lambda: 90))
        self.assertEqual(7, cache.get('seven', lambda: 7))

        self.assertHasLength(5, cache)
        # 'two' should have been removed
        self.assertIsNone(cache.get('two'))

        self.assertEqual(4, cache.pop('four'))
        self.assertHasLength(4, cache)
        self.assertIsNone(cache.pop('four'))
