from typing import Optional, Callable

from utils import date_utils
from utils.date_utils import EpochSeconds, get_epoch_seconds_in_future, determine_next_minute_time, \
    seconds_left_in_minute

Scheduler = Callable[[EpochSeconds], None]
Invoker = Callable[[], None]
UpdateNotifier = Callable[[], None]


class LambdaTimer:
    def __init__(self,
                 idle_seconds: int,
                 max_idle_seconds: Optional[int],
                 schedule_seconds: int,
                 max_seconds: int,
                 scheduler: Scheduler,
                 invoker: Invoker,
                 update_notifier: UpdateNotifier
                 ):
        """
        Construct a new alarm.

        :param idle_seconds: indicates the desired number of seconds of being idle before we should schedule an invocation.
        :param max_idle_seconds: maximum idle seconds. Since we have to schedule to the next minute, and typically do not
        want to delay for a minute, we'll do so if we exceed this max idle seconds.
        :param schedule_seconds: when it is determined that we want to schedule an invocation due to inactivity,
        the number of seconds in the future the invocation should be scheduled for.
        :param max_seconds: maximum seconds before an immediate invocation is needed (899 is max)
        :param scheduler: scheduler to invoke when a schedule should be done.
        :param invoker: invoker to call to invoke immediately
        :param update_notifier: Called when an update should be done.
        """
        assert max_seconds < 900, "max_seconds should be less than 900"
        now = date_utils.get_system_time_in_millis()
        self.__end_time = get_epoch_seconds_in_future(max_seconds, from_time=now)
        self.__idle_target = get_epoch_seconds_in_future(idle_seconds, from_time=now, round_to_minute=True)
        self.__idle_seconds = idle_seconds
        self.__max_idle_millis = max_idle_seconds * 1000 \
            if max_idle_seconds is not None and max_idle_seconds > 0 else None
        self.__schedule_seconds = schedule_seconds
        self.__scheduler = scheduler
        self.__invoker = invoker
        self.__update_notifier = update_notifier
        self.__done = False
        self.__last_activity_time = date_utils.get_system_time_in_millis()
        self.__schedule_target: Optional[EpochSeconds] = None
        self.__check_time: Optional[EpochSeconds] = None
        self.__delay_seconds: Optional[int] = None

    def get_delay_time_seconds(self, default_value: int) -> Optional[int]:
        """
        Determine a delay seconds based on next idle target time and next max time.

        :param default_value: the desired seconds.
        :return: the minimum delay to use None means we are done.
        """
        assert default_value > 0
        if self.is_done():
            return None
        return min(self.__delay_seconds, default_value)

    def clear_idle(self):
        """
        Indicate activity and reset the next idle target time.
        """
        now = date_utils.get_system_time_in_millis()
        self.__last_activity_time = now
        self.__idle_target = get_epoch_seconds_in_future(self.__idle_seconds, from_time=now, round_to_minute=True)
        self.__schedule_target = None

    def seconds_idle(self) -> int:
        """
        The number of seconds of idle time.

        :return: idle time.
        """
        return (date_utils.get_system_time_in_millis() - self.__last_activity_time) // 1000

    def has_time_left(self, seconds: int) -> bool:
        assert seconds > 0
        if self.__done:
            return False
        time_left = self.__end_time - date_utils.get_system_time_in_seconds()
        if time_left < seconds:
            self.__set_done()
            self.__invoker()
            return False
        return True

    def set_done(self):
        if not self.__done:
            self.__set_done()

    def __set_done(self):
        self.__done = True
        if self.__update_notifier is not None:
            self.__update_notifier()

    def is_done(self) -> bool:
        """
        Whether the timer is done (stop doing whatever you are doing).

        :return: True if the timer is done.
        """
        if self.__done:
            return True

        self.__check_time = now = date_utils.get_system_time_in_seconds()
        if now >= self.__end_time:
            self.__set_done()
            self.__invoker()
            return True

        diff = self.__idle_target - now
        if diff <= 0:
            target_time = determine_next_minute_time(self.__schedule_seconds, from_time=now * 1000,
                                                     flex_seconds=1)
            if (target_time - now <= self.__schedule_seconds or
                    (now * 1000) - self.__last_activity_time > self.__max_idle_millis):
                self.__set_done()
                self.__scheduler(target_time)
                return True
            self.__delay_seconds = max(seconds_left_in_minute(now), 1)
        else:
            self.__delay_seconds = diff

        return False
