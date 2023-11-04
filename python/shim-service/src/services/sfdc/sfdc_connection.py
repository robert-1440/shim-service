import abc
import pickle
from typing import Dict, Optional, Any

from bean import BeanName
from bean.beans import inject
from lambda_web_framework.web_exceptions import NotAuthorizedException, LambdaHttpException
from services.sfdc import SfdcAuthenticator
from services.sfdc.live_agent import live_agent
from services.sfdc.live_agent.live_agent import LiveAgent
from services.sfdc.types import preload_actions
from services.sfdc.types.aura_context import AuraSettings
from utils import loghelper, exception_utils
from utils.http_client import HttpClient, HttpResponse, ClientBuilder, RequestBuilder
from utils.salesforce_utils import extract_sf_sub_domain, extract_aura_token
from utils.uri_utils import form_https_uri, Uri

logger = loghelper.get_logger(__name__)


class SfdcConnection(metaclass=abc.ABCMeta):
    organization_id: str
    lightning_domain: str

    @abc.abstractmethod
    def load_live_agent(self) -> LiveAgent:
        raise NotImplementedError()

    @abc.abstractmethod
    def http_call(self, rb: RequestBuilder, base_url: str = None) -> HttpResponse:
        raise NotImplementedError()

    @abc.abstractmethod
    def serialize(self) -> bytes:
        raise NotImplementedError()

    @abc.abstractmethod
    def get_lightning_session_id(self) -> str:
        raise NotImplementedError()


class _SfdcConnectionImpl(SfdcConnection):
    def __init__(self,
                 authenticator: SfdcAuthenticator,
                 client: HttpClient):
        self.client = client
        self.instance_uri = authenticator.instance_uri
        self.session_ids_by_host: Dict[str, str] = {}
        self.aura_settings = AuraSettings()
        self.__organization_id: Optional[str] = None
        sub_domain = extract_sf_sub_domain(authenticator.instance_uri)
        self.__lightning_domain = f"{sub_domain}.lightning.force.com"
        self.my_domain = f"{sub_domain}.my.salesforce.com"

    def get_lightning_session_id(self) -> str:
        return self.session_ids_by_host.get(self.__lightning_domain)

    @property
    def organization_id(self) -> str:
        return self.__organization_id

    @property
    def lightning_domain(self) -> str:
        return self.__lightning_domain

    def http_call(self, rb: RequestBuilder, base_url: str = None) -> HttpResponse:
        return rb.send(self.client, base_url=base_url)

    def __deserialized(self, client: HttpClient):
        self.client = client

    def __verify_attributes(self):
        bad_list = []

        def verify(value: Any, name: str):
            if value is None:
                bad_list.append(name)

        aura = self.aura_settings
        verify(aura.aura_context, "Aura Context")
        verify(self.__organization_id, "Organization Id")
        verify(aura.fwuid, "Framework Id")
        if len(self.session_ids_by_host) == 0:
            bad_list.append("Session Id")
        if len(bad_list) > 0:
            self.client.log_cookies(logger)
            raise NotAuthorizedException("Salesforce auth failed, unable "
                                         f"to find the following attributes: {', '.join(bad_list)}")

    def __auth(self, access_token: str):
        def inner():
            self.__invoke_uri(
                form_https_uri(self.instance_uri.host,
                               'secur/frontdoor.jsp',
                               {'sid': access_token}))

            self.__invoke_uri(
                form_https_uri(self.instance_uri.host,
                               'visualforce/session',
                               {'url': f'https://{self.__lightning_domain}/one/one.app'})
            )

        try:
            inner()
            # Make sure all attributes are set
            self.__verify_attributes()
            return
        except LambdaHttpException as ex:
            raise ex
        except Exception:
            logger.warning(f"Failed to auth: {exception_utils.dump_ex()}")
        raise NotAuthorizedException("Salesforce authentication failed.")

    def __preload_actions(self):
        logger.info("Preloading Salesforce Context ...")
        preload_actions.load(self.aura_settings, self.client, self.__lightning_domain)

    def __created(self, access_token: str):
        self.__auth(access_token)
        try:
            self.__preload_actions()
        except Exception as ex:
            logger.error(f"Failed loading Salesforce data: {exception_utils.dump_ex()}")
            raise LambdaHttpException(502, f"Failed on Salesforce call: {ex}")

    def load_live_agent(self) -> LiveAgent:
        return live_agent.load_live_agent(self.aura_settings,
                                          self.__lightning_domain,
                                          self.client)

    def __load_aura_context(self, response: HttpResponse):
        if self.aura_settings.fwuid is not None and self.aura_settings.aura_context is None:
            return
        self.aura_settings.parse_links(response)

    def __invoke_uri(self, uri: Uri):
        counter = 0
        aura = self.aura_settings
        while counter < 31:
            origin_uri: Uri = Uri.parse(uri.origin)
            response = self.client.get(uri.to_url(), allow_redirects=False)

            if aura.aura_token is None:
                aura.aura_token = extract_aura_token(self.client)
            if aura.fwuid is None or aura.aura_context is None:
                self.__load_aura_context(response)
            sid = self.client.find_cookie_value_by_uri(origin_uri, 'sid')
            if sid is not None:
                self.session_ids_by_host[origin_uri.host] = sid
            if self.__organization_id is None:
                self.__organization_id = self.client.find_cookie_value_by_uri(origin_uri, 'oid')

            if not response.is_redirect:
                return response

            uri = Uri.parse(response.get_header('location'))
            counter += 1
        raise LambdaHttpException(421, "Too many re-directs.")

    def serialize(self) -> bytes:
        save_client = self.client
        save_aura = self.aura_settings
        try:
            self.client = None
            self.aura_settings = None
            return pickle.dumps(self)
        finally:
            self.client = save_client
            self.aura_settings = save_aura

    def __eq__(self, other):
        if not isinstance(other, _SfdcConnectionImpl):
            return False

        return (
                self.instance_uri == other.instance_uri and
                self.session_ids_by_host == other.session_ids_by_host and
                self.__organization_id == other.__organization_id and
                self.__lightning_domain == other.__lightning_domain and
                self.my_domain == other.my_domain
        )


@inject(bean_instances=BeanName.HTTP_CLIENT_BUILDER)
def create_new_connection(authenticator: SfdcAuthenticator,
                          builder: ClientBuilder) -> SfdcConnection:
    impl = _SfdcConnectionImpl(
        authenticator,
        builder()
    )
    getattr(impl, "_SfdcConnectionImpl__created")(authenticator.get_access_token())
    return impl


@inject(bean_instances=BeanName.HTTP_CLIENT_BUILDER)
def deserialize(data: bytes, builder: ClientBuilder) -> SfdcConnection:
    impl: _SfdcConnectionImpl = pickle.loads(data)
    getattr(impl, "_SfdcConnectionImpl__deserialized")(builder())
    return impl
