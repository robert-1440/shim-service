from typing import Any, List, Dict

from lambda_web_framework.web_exceptions import BadRequestException

_CHANNELS = {}


class PlatformChannel(str):
    def __init__(self, name: str):
        self.__name = name
        _CHANNELS[name.lower()] = self

    @property
    def name(self) -> str:
        return self.__name

    def __str__(self):
        return self.__name


OMNI_PLATFORM = PlatformChannel('omni')
X1440_PLATFORM = PlatformChannel('x1440')


def get_platform_channel(name: str) -> PlatformChannel:
    channel = _CHANNELS.get(name.lower())
    if channel is None:
        raise BadRequestException(f"Channel type '{name}' is invalid. Must be one of {', '.join(_CHANNELS.keys())}.")
    return channel


def assert_valid_platform_channel(name: str) -> bool:
    get_platform_channel(name)
    return True


def deserialize_platform_channels(record: Dict[str, Any]) -> List[str]:
    results = []
    for channel in _CHANNELS.keys():
        if record.get(f'pt_{channel}'):
            results.append(channel)
    return results


def serialize_platform_channels(channel_types: List[str], record: Dict[str, Any]):
    for pt in channel_types:
        record[f"pt_{pt}"] = True
