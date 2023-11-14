import time

from better_test_case import BetterTestCase
from utils.throttler import Throttler


class TestSuite(BetterTestCase):

    def test_it(self):
        hit_count = 0

        def caller():
            nonlocal hit_count
            hit_count += 1

        throttler = Throttler(100, caller)
        throttler.add_invocation()
        throttler.add_invocation()
        throttler.add_invocation()
        time.sleep(.010)
        throttler.add_invocation()

        time.sleep(0.2)
        self.assertEqual(1, hit_count)
        throttler.add_invocation()
        self.assertEqual(1, hit_count)

        t = getattr(throttler, "_Throttler__thread")
        self.assertTrue(t.is_alive())

        throttler.close()
        self.assertEqual(2, hit_count)

        self.assertRaises(AssertionError, throttler.add_invocation)

        self.assertFalse(t.is_alive())

    def test_with_exception(self):
        """
        Make sure that when an exception raised in the caller, it does not cause problems.
        """
        hit_count = 0

        def caller():
            nonlocal hit_count
            hit_count += 1
            raise ValueError("OK")

        throttler = Throttler(100, caller)
        throttler.add_invocation()
        throttler.close()
        self.assertEqual(1, hit_count)

    def test_no_thread(self):
        hit_count = 0

        def caller():
            nonlocal hit_count
            hit_count += 1

        throttler = Throttler(100, caller)
        throttler.close()
        self.assertEqual(0, hit_count)
