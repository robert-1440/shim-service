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
