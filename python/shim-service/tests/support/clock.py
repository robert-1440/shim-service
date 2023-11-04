from typing import Dict, Any

from utils import date_utils
from utils.date_utils import EpochMilliseconds, EpochSeconds


class Clock:
    def __init__(self):
        self.ticks = 0
        self.__attributes: Dict[str, Any] = {}
        self.__install()
        self.cleaned_up = False

    def set_mm_ss(self, mmss: int):
        self.ticks = (((mmss // 100) * 60) + (mmss % 100)) * 1000

    def increment_ticks(self, ticks: int):
        self.ticks += ticks

    def increment_seconds(self, seconds: int):
        self.ticks += seconds * 1000

    def __install(self):
        self.__set('get_system_time_in_millis', self.__get_system_time_in_millis)
        self.__set('get_system_time_in_seconds', self.__get_system_time_in_seconds)

    def __set(self, name: str, value: Any):
        self.__attributes[name] = getattr(date_utils, name)
        setattr(date_utils, name, value)

    def __get_system_time_in_millis(self) -> EpochMilliseconds:
        assert not self.cleaned_up
        return self.ticks

    def __get_system_time_in_seconds(self) -> EpochSeconds:
        assert not self.cleaned_up
        return self.ticks // 1000

    def cleanup(self):
        self.cleaned_up = True
        for att, value in self.__attributes.items():
            setattr(date_utils, att, value)
