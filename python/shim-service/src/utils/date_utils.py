import sys
import time
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple, Union

import dateutil.parser as date_parser

EpochMilliseconds = int
EpochSeconds = int


def millis_to_timestamp(millis: int) -> Optional[datetime]:
    if millis is None:
        return None
    seconds = millis // 1000
    ds = datetime.fromtimestamp(seconds)

    millis = millis % 1000
    if millis != 0:
        ds += timedelta(milliseconds=millis)
    return ds


def get_system_time_in_seconds() -> EpochSeconds:
    return get_system_time_in_millis() // 1000


def get_system_time_in_millis() -> EpochMilliseconds:
    if sys.version_info.major > 3 or (sys.version_info.major == 3 and sys.version_info.minor > 6):
        return time.time_ns() // 1000000
    else:
        return int(time.time() * 1000)


def get_difference_in_minutes(a: Union[int, datetime], b: Union[int, datetime]) -> int:
    return int(get_difference(a, b).total_seconds() // 60)


def get_difference_in_seconds(a: Union[int, datetime], b: Union[int, datetime]) -> int:
    return int(get_difference(a, b).total_seconds())


def get_difference_in_hours(a: Union[int, datetime], b: Union[int, datetime]) -> int:
    return int(get_difference(a, b).total_seconds() // 3600)


def get_difference(a: Union[int, datetime], b: Union[int, datetime]) -> timedelta:
    a, b = __fix_dates(a, b)
    return a - b


def get_age_in_minutes(timestamp: Union[int, datetime]) -> int:
    return get_difference_in_minutes(datetime.now(), timestamp)


def get_age_in_seconds(timestamp: Union[int, datetime]) -> int:
    return get_difference_in_seconds(datetime.now(), timestamp)


def get_age_in_hours(timestamp: Union[int, datetime]) -> int:
    return get_difference_in_hours(datetime.now(), timestamp)


def __fix_dates(a: Union[int, datetime], b: Union[int, datetime]) -> Tuple[datetime, datetime]:
    if type(a) is int:
        a = millis_to_timestamp(a)
    if type(b) is int:
        b = millis_to_timestamp(b)

    if (a.tzinfo is None) != (b.tzinfo is None):
        if a.tzinfo is None:
            a = a.astimezone(timezone.utc)
        else:
            b = b.astimezone(timezone.utc)
    return a, b


def get_epoch_seconds_in_future(seconds: int,
                                from_time: EpochMilliseconds = None,
                                round_to_minute: bool = False) -> EpochSeconds:
    current = get_system_time_in_millis() if from_time is None else from_time
    current = (current + 500) // 1000 + seconds
    if round_to_minute:
        current = round_to_next_minute(current)
    return current


def from_string(string: str, local_zone: bool = False) -> Optional[datetime]:
    if string is None:
        return None
    if string.isdigit():
        ts = millis_to_timestamp(int(string))
    else:
        ts = date_parser.parse(string)
    if local_zone:
        ts = datetime.fromtimestamp(ts.timestamp())
    return ts


def determine_next_minute_time(seconds_in_future: int,
                               from_time: EpochMilliseconds = None,
                               flex_seconds: int = 0) -> EpochSeconds:
    """
    Used to determine the next timestamp rounded to the nearest minute (never below the scheduled time).

    For example:
    Given seconds in future of 30 seconds:

    If now is 1:00:00, the schedule time will be 1:01:00
    1:00:30 => 1:01:00
    1:00:45 => 1:02:00

    :param seconds_in_future: desired seconds in the future.
    :param from_time: the start time (millis), now if None
    :param flex_seconds: the number of seconds to allow. (i.e. give or take x seconds).
    :return: the timestamp.
    """
    now = from_time if from_time is not None else get_system_time_in_millis()
    now_seconds = (now + 500) // 1000
    left = 60 - (now_seconds % 60)
    seconds_in_future -= left
    now_seconds += left
    if seconds_in_future <= 0:
        return now_seconds

    future_time = now_seconds + seconds_in_future
    diff = future_time - now_seconds
    seconds_left = diff % 60
    minutes = diff // 60
    if seconds_left > flex_seconds:
        minutes += 1
    return now_seconds + (minutes * 60)


def round_to_next_minute(stamp: EpochSeconds) -> EpochSeconds:
    return ((stamp // 60) * 60) + (60 - stamp % 60)


def seconds_left_in_minute(stamp: EpochSeconds):
    return stamp % 60


def format_elapsed_time_seconds(start_time: EpochMilliseconds) -> str:
    elapsed_time = (get_system_time_in_millis() - start_time) / 1000
    return f"{elapsed_time:.3f}"
