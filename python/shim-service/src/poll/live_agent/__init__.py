from poll import PollingPlatform
from repos import Serializable
from services.sfdc.live_agent import LiveAgentPollerSettings
from session import ContextType


class LiveAgentPlatform(PollingPlatform):

    @classmethod
    def get_context_type(cls) -> ContextType:
        return ContextType.LIVE_AGENT

    @classmethod
    def create_initial_polling_settings(cls) -> Serializable:
        return LiveAgentPollerSettings()
