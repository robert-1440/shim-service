import json
from typing import Optional, List

from services.sfdc.live_agent import omnichannel, LiveAgentStatus, API_VERSION, LiveAgentSession, API_VERSION_STRING, \
    LiveAgentPollerSettings
from services.sfdc.live_agent.scrt_info import ScrtInfo
from services.sfdc.types.aura_context import AuraSettings
from utils import loghelper
from utils.http_client import HttpClient, RequestBuilder, HttpMethod
from utils.uri_utils import Uri, form_url_from_endpoint

logger = loghelper.get_logger(__name__)


class LiveAgent:
    def __init__(self, status_options: List[LiveAgentStatus],
                 scrt_info: Optional[ScrtInfo],
                 chat_endpoint: Optional[str],
                 session: LiveAgentSession):
        self.__status_options: List[LiveAgentStatus] = status_options
        self.scrt_info: Optional[ScrtInfo] = scrt_info
        self.__chat_endpoint: Optional[str] = chat_endpoint
        self.__session = session

    @property
    def session(self) -> LiveAgentSession:
        return self.__session

    @property
    def endpoint(self) -> Optional[str]:
        if self.__chat_endpoint is not None:
            return self.__chat_endpoint
        return self.scrt_info.end_point

    @property
    def status_options(self) -> List[LiveAgentStatus]:
        return self.__status_options

    def get_client_poll_timeout(self) -> int:
        return self.__session.client_poll_timeout

    def create_poll_request_builder(self, settings: LiveAgentPollerSettings):
        url = form_url_from_endpoint(
            self.endpoint,
            "rest/System/Messages",
            query_params={
                'ack': str(settings.ack),
                'pc': str(settings.pc)
            }
        )
        logger.info(f"Client timeout seconds = {self.__session.client_poll_timeout}")
        rb = RequestBuilder(HttpMethod.GET, url).timeout_seconds(self.__session.client_poll_timeout + 1)
        if self.__session is not None:
            self.__session.add_headers(rb)
        return rb

    def __eq__(self, other):
        return (
                isinstance(other, LiveAgent) and
                self.__status_options == other.__status_options and
                self.scrt_info == other.scrt_info and
                self.__chat_endpoint == other.__chat_endpoint and
                self.__session == other.__session
        )


def __load_chat_endpoint(scrt_info: ScrtInfo,
                         client: HttpClient) -> Optional[str]:
    logger.info("Attempting to load chat URL ...")
    uri = Uri.parse(f"{scrt_info.end_point}/rest/cdm?version={API_VERSION}&redirect=true")
    resp = client.get(uri.to_url(), allow_redirects=False)
    if resp.is_redirect:
        location = Uri.parse(resp.get_location())
        return f"{location.origin}/chat"
    return None


def __load_live_agent_session(end_point: str,
                              client: HttpClient) -> LiveAgentSession:
    uri = Uri.parse(f"{end_point}/rest/System/SessionId?SessionId.ClientType=lightning")
    resp = client.get(
        uri.to_url(),
        headers={
            'X-Liveagent-Affinity': 'null',
            'X-Liveagent-Api-Version': API_VERSION_STRING
        }
    )
    return LiveAgentSession.from_record(json.loads(resp.body))


def load_live_agent(settings: AuraSettings,
                    domain: str,
                    client: HttpClient) -> LiveAgent:
    options, scrt_info = omnichannel.get_statuses_and_scrt_info(settings, domain, client)
    chat_endpoint = __load_chat_endpoint(scrt_info, client)
    session = __load_live_agent_session(scrt_info.end_point if chat_endpoint is None else chat_endpoint, client)
    return LiveAgent(options, scrt_info, chat_endpoint, session)
