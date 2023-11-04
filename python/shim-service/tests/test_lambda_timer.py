from typing import Optional
from unittest import TestCase

from support.clock import Clock
from utils.date_utils import EpochSeconds
from utils.lambda_timer import LambdaTimer


def _to_seconds(mmss: int):
    return ((mmss // 100) * 60) + (mmss % 100)


class TestLambdaTimer(TestCase):
    clock: Clock
    schedule_time: Optional[EpochSeconds]
    schedule_count: int
    invoke_count: int
    done: bool = False

    def test_idle(self):
        timer = self.create_timer(30, 600, 30)
        self.assertFalse(timer.is_done())
        self.assertEqual(0, self.invoke_count)
        self.assertEqual(0, self.schedule_count)
        self.assertFalse(self.done)

        # Get delay time using 10 as the default, since 30 is the idle mark, 10 should be used
        self.assertEqual(10, timer.get_delay_time_seconds(10))

        # Get delay time using 40 as the default, since 30 is the idle mark, 30 should be used
        self.assertEqual(30, timer.get_delay_time_seconds(40))

        # Set the current time to 00:41, exceeding the idle seconds, but we cannot schedule
        # because it would exceed the limit
        self.clock.set_mm_ss(41)
        self.assertFalse(timer.is_done())
        self.assertEqual(0, self.schedule_count)
        self.assertEqual(41, timer.seconds_idle())

        self.clock.set_mm_ss(0)
        timer.clear_idle()
        self.assertEqual(0, timer.seconds_idle())

        # Now set it to a timestamp where we CAN schedule 00:30
        self.clock.set_mm_ss(30)
        self.assertTrue(timer.is_done())
        self.assertEqual(1, self.schedule_count)
        self.assertEqual(0, self.invoke_count)

        # Ensure the schedule time was for the next minute
        self.assertEqual(60, self.schedule_time)

        # Make sure we don't schedule again
        self.assertTrue(timer.is_done())
        self.assertEqual(1, self.schedule_count)
        self.assertEqual(0, self.invoke_count)

    def test_max_idle(self):
        timer = self.create_timer(30, 600, 30)
        # Start time was 0:00
        # Set minute to 10:01
        self.clock.set_mm_ss(1001)
        self.assertEqual(601, timer.seconds_idle())

        self.assertIsNone(timer.get_delay_time_seconds(10))
        self.assertTrue(timer.is_done())
        self.assertEqual(1, self.schedule_count)
        self.assertTrue(self.done)

        # Make sure it scheduled it @ 11:00
        self.assertEqual(_to_seconds(1100), self.schedule_time)
        self.assertEqual(0, self.invoke_count)

    def test_no_time_left(self):
        timer = self.create_timer(30, 600, 30,
                                  max_seconds=700)
        self.assertTrue(timer.has_time_left(699))
        self.assertFalse(self.invoke_count)

        self.assertFalse(timer.has_time_left(701))
        self.assertTrue(self.invoke_count)

    def test_invoke(self):
        timer = self.create_timer(30, 600, 30,
                                  max_seconds=700)
        # Start time was 0:00
        self.clock.ticks = 700000
        self.assertTrue(timer.is_done())
        self.assertEqual(1, self.invoke_count)

        self.assertIsNone(timer.get_delay_time_seconds(10))
        self.assertTrue(timer.is_done())
        self.assertEqual(1, self.invoke_count)
        self.assertTrue(self.done)

    def notifier(self):
        assert not self.done
        self.done = True

    def schedule(self, stamp: int):
        self.schedule_time = stamp
        self.schedule_count += 1

    def invoke(self):
        self.invoke_count += 1

    def create_timer(self, idle_seconds: int,
                     max_idle_seconds: Optional[int],
                     schedule_seconds: int,
                     max_seconds: int = 899,
                     ):
        t = LambdaTimer(
            idle_seconds,
            max_idle_seconds,
            schedule_seconds,
            max_seconds=max_seconds,
            scheduler=self.schedule,
            invoker=self.invoke,
            update_notifier=self.notifier
        )
        return t

    def setUp(self):
        self.clock = Clock()
        self.schedule_time = None
        self.invoke_count = 0
        self.schedule_count = 0

    def tearDown(self):
        self.clock.cleanup()
