import abc
from copy import copy
from typing import List, Optional, Any, Dict

from bean import BeanName
from bean.beans import inject
from events.event_types import EventType
from lambda_web_framework.web_exceptions import InvalidParameterException
from repos.resource_lock import ResourceLock, ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from services.sfdc.live_agent import LiveAgentWebSettings, PresenceStatus, StatusOption
from services.sfdc.live_agent.api import presence_status
from services.sfdc.sfdc_session import SfdcSession, SfdcSessionAndContext, load_with_context
from session import Session, SessionContext, ContextType
from utils import loghelper, collection_utils
from utils.http_client import HttpMethod

logger = loghelper.get_logger(__name__)


class OmniChannelApi(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_presence_statuses(self) -> List[PresenceStatus]:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_presence_status(self, status: str):
        raise NotImplementedError()

    @abc.abstractmethod
    def accept_work(self, work_id: str, work_target_id: str):
        raise NotImplementedError()

    @abc.abstractmethod
    def decline_work(self, work_id: str, decline_reason: Optional[str]):
        raise NotImplementedError()

    @abc.abstractmethod
    def close_work(self, work_id: str):
        raise NotImplementedError()


class _OmniChannelApi(OmniChannelApi):
    def __init__(self,
                 sfdc_session: SfdcSession,
                 sfdc_context: SessionContext,
                 resource_lock: ResourceLock,
                 repo: SessionContextsRepo):
        self.repo = repo
        self.sfdc_session = sfdc_session
        self.sfdc_context = sfdc_context
        self.settings = LiveAgentWebSettings.deserialize(sfdc_context.session_data)
        self.initial_settings = copy(self.settings)
        self.resource_lock = resource_lock

    @staticmethod
    def build_presence_uri(resource_type: str):
        return "rest/Presence/" + resource_type

    def get_presence_statuses(self) -> List[PresenceStatus]:
        return self.sfdc_session.get_presence_statuses()

    def set_presence_status(self, status_id: str):
        match: PresenceStatus = collection_utils.find_first_match(self.sfdc_session.get_presence_statuses(),
                                                                  lambda m: m.id == status_id)
        if match is None:
            raise InvalidParameterException("id", f"'{status_id}' is invalid.")

        if match.status_option == StatusOption.OFFLINE:
            resource_type = "Logout"
        else:
            resource_type = "Login"

        body = presence_status.construct_set_presence_status_body(self.sfdc_session, match.id)
        self.__invoke_presence_request(
            "Presence" + resource_type,
            EventType.PRESENCE_STATUS_SET,
            {'status': match.status_option.name},
            body
        )

    def accept_work(self, work_id: str, work_target_id: str):
        event_data = {
            'workId': work_id,
            'workTargetId': work_target_id
        }
        self.__invoke_presence_request(
            "AcceptWork",
            EventType.WORK_ACCEPTED,
            event_data,
            event_data
        )

    def decline_work(self, work_id: str, decline_reason: Optional[str]):
        event_data = {
            'workId': work_id
        }
        if decline_reason is not None:
            event_data['declineReason'] = decline_reason
        self.__invoke_presence_request(
            "DeclineWork",
            EventType.WORK_DECLINED,
            event_data,
            event_data
        )

    def close_work(self, work_id: str):
        event_data = {
            'workId': work_id
        }
        self.__invoke_presence_request(
            "CloseWork",
            EventType.WORK_CLOSED,
            event_data,
            event_data
        )

    def __invoke_presence_request(self,
                                  action: str,
                                  event_type: EventType,
                                  event_data: Optional[Dict[str, Any]],
                                  body: Dict[str, Any]):
        uri = self.build_presence_uri(action)
        resp = self.sfdc_session.send_web_request_with_event(
            event_type,
            event_data,
            self.settings,
            HttpMethod.POST,
            uri,
            body
        )
        logger.info(f"Response to {action} request: {resp.to_string()}")

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.settings != self.initial_settings:
                context = self.sfdc_context.set_session_data(self.settings.serialize())
                self.repo.update_session_context(context)
        finally:
            self.resource_lock.release()


@inject(bean_instances=(BeanName.RESOURCE_LOCK_REPO, BeanName.SESSION_CONTEXTS_REPO))
def load_api(
        session: Session,
        resource_lock_repo: ResourceLockRepo,
        contexts_repo: SessionContextsRepo
) -> OmniChannelApi:
    lock_name = f"web-session/{session.tenant_id}/{session.session_id}"
    lock, sc = resource_lock_repo.acquire_and_execute(lock_name, 1, 30,
                                                      lambda: load_with_context(session, ContextType.WEB))
    sc: SfdcSessionAndContext
    return lock.execute_and_release_on_exception(lambda:
                                                 _OmniChannelApi(sc.session,
                                                                 sc.context,
                                                                 lock,
                                                                 contexts_repo))
