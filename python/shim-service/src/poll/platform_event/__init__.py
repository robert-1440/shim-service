from poll import PollingPlatform
from session import ContextType


class X1440Platform(PollingPlatform):

    @classmethod
    def get_context_type(cls):
        return ContextType.X1440

    @classmethod
    def create_initial_polling_settings(cls):
        return X1440PollerSettings()