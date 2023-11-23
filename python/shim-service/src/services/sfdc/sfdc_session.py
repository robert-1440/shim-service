import abc
import json
import pickle
from typing import Optional, List, Dict, Any, Union

from bean import BeanName, inject
from events.event_types import EventType
from repos.sessions_repo import store_event
from repos.sfdc_sessions_repo import SfdcSessionsRepo
from services.sfdc import SfdcAuthenticator, create_authenticator
from services.sfdc.live_agent import PresenceStatus, LiveAgentPollerSettings, LiveAgentWebSettings
from services.sfdc.live_agent.live_agent import LiveAgent
from services.sfdc.live_agent.message_data import MessageData
from services.sfdc.sfdc_connection import SfdcConnection, create_new_connection, deserialize as deserialize_conn
from session import Session, ContextType, SessionContext, SessionKey
from utils import loghelper
from utils.date_utils import get_system_time_in_millis
from utils.exception_utils import dump_ex
from utils.http_client import HttpResponse, RequestBuilder, HttpMethod
from utils.perf_timer import timer, execute_and_log

logger = loghelper.get_logger(__name__)

TESTING = False


class SfdcSession(SessionKey, metaclass=abc.ABCMeta):
    tenant_id: int
    session_id: str
    user_id: str
    organization_id: str
    lightning_domain: str
    expiration_seconds: int

    @abc.abstractmethod
    def get_presence_statuses(self) -> List[PresenceStatus]:
        raise NotImplementedError()

    @abc.abstractmethod
    def serialize(self) -> bytes:
        raise NotImplementedError()

    @abc.abstractmethod
    def poll_live_agent(self, settings: LiveAgentPollerSettings) -> Optional[MessageData]:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_live_agent_poll_timeout_seconds(self) -> int:
        raise NotImplementedError()

    @abc.abstractmethod
    def send_web_request(self, web_settings: LiveAgentWebSettings,
                         method: HttpMethod,
                         uri: str,
                         body: Union[dict, str] = None,
                         response_on_error: bool = False,
                         headers: Dict[str, str] = None) -> HttpResponse:
        raise NotImplementedError()

    def send_web_request_with_event(self,
                                    event_type: EventType,
                                    event_data: Dict[str, Any],
                                    web_settings: LiveAgentWebSettings,
                                    method: HttpMethod,
                                    uri: str,
                                    body: Union[dict, str] = None,
                                    headers: Dict[str, str] = None) -> HttpResponse:
        start_time = get_system_time_in_millis()
        resp = self.send_web_request(
            web_settings,
            method,
            uri,
            body=body,
            response_on_error=True,
            headers=headers
        )
        elapsed = get_system_time_in_millis() - start_time
        logger.info(f"Web request to {method} {uri} took {elapsed} ms.")

        event_data = dict(event_data) if event_data is not None else {}
        event_data['userId'] = self.user_id
        event_data['sessionId'] = self.session_id
        event_data['sfdcResponse'] = resp.status_code
        event_data['sfdcTime'] = elapsed

        execute_and_log(logger, f"Store {event_type.name} event",
                        lambda: store_event(
                            self,
                            self.user_id,
                            self.expiration_seconds,
                            event_type,
                            event_data
                        ))
        if not resp.is_2xx():
            resp.check_exception()
        return resp

    def describe(self) -> str:
        return f"{self.tenant_id}#{self.session_id}"

    def to_invocation_event(self) -> Dict[str, Any]:
        return {
            'tenantId': self.tenant_id,
            'sessionId': self.session_id
        }

    @abc.abstractmethod
    def get_lightning_session_id(self) -> str:
        raise NotImplementedError()

    def key_for_logging(self):
        return f"{self.tenant_id}-{self.session_id}"


class _Blob:
    def __init__(self, conn_data: bytes, live_agent_bytes: bytes):
        self.conn_data = conn_data
        self.live_agent_bytes = live_agent_bytes

    def __len__(self):
        return len(self.conn_data) + len(self.live_agent_bytes)


class SfdcSessionAndContext:
    def __init__(self, session: SfdcSession, context: SessionContext):
        self.session = session
        self.context = context


class _SfdcSessionImpl(SfdcSession):
    conn: SfdcConnection

    def __init__(self):
        self.tenant_id: Optional[int] = None
        self.session_id: Optional[str] = None
        self.conn: Optional[SfdcConnection] = None
        self.live_agent: Optional[LiveAgent] = None
        self.expiration_seconds: Optional[int] = None
        self.user_id: Optional[str] = None

    def get_presence_statuses(self) -> List[PresenceStatus]:
        return list(map(lambda o: o.to_presence_status(), self.live_agent.status_options))

    def serialize(self) -> bytes:
        blob = _Blob(self.conn.serialize(), pickle.dumps(self.live_agent))
        return pickle.dumps(blob)

    def get_live_agent_poll_timeout_seconds(self) -> int:
        return self.live_agent.get_client_poll_timeout()

    def poll_live_agent(self, settings: LiveAgentPollerSettings) -> Optional[MessageData]:
        rb = self.live_agent.create_poll_request_builder(settings).allow_response_on_error(True)
        start = get_system_time_in_millis()
        try:
            resp = self.conn.http_call(rb)
        except BaseException as ex:
            logger.severe(f"Exception polling live agent: {dump_ex(ex)}")
            return MessageData.create_live_agent_kit_shutdown_data(settings.ack)

        elapsed = get_system_time_in_millis() - start
        logger.info(f"{self.key_for_logging()}: Poll response to {rb.get_uri()} "
                    f"(elapsed = {elapsed} ms.):\n{resp.to_string()}")

        settings.pc += 1
        if resp.status_code == 200:
            return MessageData.from_record(json.loads(resp.body))
        # Not sure what this is about, but the Dart code seems to want to fail if the response time is
        # less than 5 seconds, so we'll do the same. ¯\_(ツ)_/¯
        if elapsed < 5000:
            if resp.status_code == 204 and TESTING:
                return None
            return MessageData.create_live_agent_kit_shutdown_data(settings.ack)
        return None

    def send_web_request(self, web_settings: LiveAgentWebSettings,
                         method: HttpMethod,
                         uri: str,
                         body: Union[dict, str] = None,
                         response_on_error: bool = False,
                         headers: Dict[str, str] = None) -> HttpResponse:
        rb = RequestBuilder(method, uri).allow_response_on_error(response_on_error)
        if headers is not None:
            rb.headers(headers)
        self.live_agent.session.add_headers(rb)
        web_settings.add_headers(rb)

        if body is not None:
            rb.body(body)

        return self.conn.http_call(rb, self.live_agent.endpoint)

    def get_lightning_session_id(self) -> str:
        return self.conn.get_lightning_session_id()

    @property
    def organization_id(self) -> str:
        return self.conn.organization_id

    @property
    def lightning_domain(self) -> str:
        return self.conn.lightning_domain

    def __eq__(self, other):
        if not isinstance(other, _SfdcSessionImpl):
            return False
        return (
                self.tenant_id == other.tenant_id and
                self.session_id == other.session_id and
                self.conn == other.conn and
                self.live_agent == other.live_agent
        )


def create_sfdc_session_from_session(session: Session) -> SfdcSession:
    return create_sfdc_session(create_authenticator(session))


@timer(logger, "Create SFDC Session")
def create_sfdc_session(authenticator: SfdcAuthenticator) -> SfdcSession:
    impl = _SfdcSessionImpl()
    impl.tenant_id = authenticator.tenant_id
    impl.session_id = authenticator.session_id
    impl.conn = create_new_connection(authenticator)
    impl.live_agent = impl.conn.load_live_agent()
    impl.expiration_seconds = authenticator.expiration_seconds
    return impl


def deserialize(key: SessionKey, user_id: str, data: bytes, expiration_seconds: int) -> SfdcSession:
    impl = _SfdcSessionImpl()
    impl.tenant_id = key.tenant_id
    impl.session_id = key.session_id
    impl.user_id = user_id
    blob: _Blob = pickle.loads(data)
    impl.conn = deserialize_conn(blob.conn_data)
    impl.live_agent = pickle.loads(blob.live_agent_bytes)
    impl.expiration_seconds = expiration_seconds
    return impl


@inject(bean_instances=BeanName.SFDC_SESSIONS_REPO)
def load_with_context(
        key: SessionKey,
        context_type: ContextType,
        sfdc_sessions_repo: SfdcSessionsRepo) -> Optional[SfdcSessionAndContext]:
    result = sfdc_sessions_repo.load_data_and_context(key, context_type)
    if result is None:
        return None
    return SfdcSessionAndContext(
        deserialize(key, result.context.user_id, result.data, result.expiration_seconds),
        result.context
    )
