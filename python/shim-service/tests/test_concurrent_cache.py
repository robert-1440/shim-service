from typing import Any

from better_test_case import BetterTestCase
from support import thread_utils
from support.thread_utils import SignalEvent
from utils.concurrent_cache import ConcurrentTtlCache


class CacheTests(BetterTestCase):

    def test_it(self):
        cache = ConcurrentTtlCache(5, 5)
        cache['one'] = 1
        cache['two'] = 2
        self.assertEqual(3, cache.get('three', lambda: 3))
        self.assertEqual(3, cache.get('three'))
        self.assertEqual(3, cache.find('three'))
        self.assertEqual(3, cache.get('three', lambda: 4))
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

        self.assertEqual(3, cache.invalidate('three'))
        self.assertHasLength(4, cache)
        self.assertIsNone(cache.get('three'))

        hit = None

        def hitter(value: Any):
            nonlocal hit
            hit = value

        cache.invalidate('seven', action=hitter)
        self.assertEqual(7, hit)
        hit = None
        cache.invalidate('seven', action=hitter)
        self.assertIsNone(hit)

        cache.clear()
        self.assertEmpty(cache)

    def test_with_threads(self):
        maxsize = 100
        object_count = 1000
        cache = ConcurrentTtlCache(maxsize, 5, lambda a: a)
        event = SignalEvent(manual_reset=True)

        """
        Do our best to test with threading.
        """

        def worker():
            event.assert_wait(1000)
            for i in range(object_count):
                self.assertEqual(i, cache.get(i))
                cache.invalidate(i)
                self.assertEqual(i, cache.get(i))

        threads = thread_utils.start_threads(worker, 10)
        event.notify()

        for t in threads:
            self.assertTrue(thread_utils.join(t, 3))

        self.assertHasLength(maxsize, cache)
        for i in range(maxsize):
            key = object_count - (i + 1)
            self.assertEqual(key, cache.find(key))

    def test_with_loader(self):
        cache = ConcurrentTtlCache(5, 5, lambda a: a)
        self.assertEqual('a', cache.get('a'))
        self.assertIsNone(cache.find('b'))

        # Simulate expiration
        internal = getattr(cache, '_ConcurrentTtlCache__cache')
        entry = internal.get('a')
        entry.expire_at -= 6

        self.assertIsNone(cache.find('a'))
        self.assertEqual('a', cache.get('a'))
