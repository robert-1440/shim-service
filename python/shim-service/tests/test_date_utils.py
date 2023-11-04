from better_test_case import BetterTestCase
from utils.date_utils import determine_next_minute_time


class DateTests(BetterTestCase):

    def test_next_minute_time(self):
        # Simulate 00 second
        self.execute(0, 10, 60)

        # Simulate 10 second
        self.execute(45, 10, 60)

        # Simulate 45 second, with interval of 20 seconds
        # 11:00:45 -> 11:02:00 otherwise we'd only result in 15 seconds from now vs the desired 20)
        self.execute(45, 20, 120)

        # Here, even though we desire 15 seconds from now, we allow for 14 seconds
        self.execute(46, 15, 60, flex_seconds=1)

    def execute(self, now: int, seconds: int, expected: int, flex_seconds: int = 0):
        self.assertEqual(expected, determine_next_minute_time(seconds, now * 1000, flex_seconds=flex_seconds))
