import time


class Timer:
    def __init__(self, timeout: float):
        self.end_time = time.time() + timeout

    def is_expired(self) -> bool:
        return time.time() >= self.end_time

    def has_time_left(self) -> bool:
        return not self.is_expired()

    def get_delay_time(self, desired: float) -> float:
        return min(max(0.0, self.end_time - time.time()), desired)

    def get_delay_time_millis(self, desired: int) -> int:
        return int(self.get_delay_time(desired / 1000) * 1000)
