import abc
from copy import copy
from typing import List, Optional, Any, Dict, Union

from bean import BeanName
from bean.beans import inject
from events.event_types import EventType
from lambda_web_framework.web_exceptions import InvalidParameterException
from repos.resource_lock import ResourceLock, ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from repos.work_id_map_repo import WorkIdMapRepo
from services.sfdc.live_agent import LiveAgentWebSettings, PresenceStatus, StatusOption
from services.sfdc.live_agent.api import presence_status
from services.sfdc.sfdc_session import SfdcSession, SfdcSessionAndContext, load_with_context
from session import Session, SessionContext, ContextType
from utils import loghelper, collection_utils
from utils.http_client import HttpMethod, HttpResponse

logger = loghelper.get_logger(__name__)


class MessageAttachment:
    def __init__(self, key: str, value: str):
        self.key = key
        self.value = value

    def to_record(self) -> Dict[str, str]:
        return {self.key: self.value}


class WorkMessage:
    def __init__(self,
                 work_target_id: str,
                 message_id: str,
                 message_body: str,
                 attachments: Optional[List[MessageAttachment]]
                 ):
        self.work_target_id = work_target_id
        self.message_id = message_id
        self.message_body = message_body
        self.attachments = attachments

    def to_body(self, work_id: str) -> dict:
        body: Dict[str, Any] = {
            'channelType': 'lmagent',
            'workId': work_id,
            'intent': 'HUMAN_AGENT',
            'messageId': self.message_id
        }
        if self.attachments is not None:
            body['attachments'] = list(map(lambda a: a.to_record(), self.attachments))
            body['text'] = None
        else:
            body['text'] = self.message_body
            body['attachments'] = []

        return body


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
    def decline_work(self, work_id: str, work_target_id: str, decline_reason: Optional[str]):
        raise NotImplementedError()

    @abc.abstractmethod
    def close_work(self, work_target_id: str):
        raise NotImplementedError()

    @abc.abstractmethod
    def send_work_message(self, message: WorkMessage):
        raise NotImplementedError()


class _OmniChannelApi(OmniChannelApi):
    def __init__(self,
                 sfdc_session: SfdcSession,
                 sfdc_context: SessionContext,
                 resource_lock: ResourceLock,
                 repo: SessionContextsRepo,
                 work_id_repo: WorkIdMapRepo):
        self.work_id_repo = work_id_repo
        self.repo = repo
        self.sfdc_session = sfdc_session
        self.sfdc_context = sfdc_context
        self.settings = LiveAgentWebSettings.deserialize(sfdc_context.session_data)
        self.initial_settings = copy(self.settings)
        self.resource_lock = resource_lock
        self.work_id_repo = work_id_repo

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

    def decline_work(self, work_id: str, work_target_id: str, decline_reason: Optional[str]):
        event_data = {
            'workId': work_id,
            'workTargetId': work_target_id
        }
        if decline_reason is not None:
            event_data['declineReason'] = decline_reason
        self.__invoke_presence_request(
            "DeclineWork",
            EventType.WORK_DECLINED,
            event_data,
            event_data
        )

    def __end_conversation(self, work_id: str):
        self.__invoke_conversation_request(
            "ConversationEnd",
            {
                'channelType': 'lmagent',
                'workId': work_id
            }
        )

    def __post(self, uri: str,
               body: Union[str, Dict[str, Any]],
               response_on_error=False,
               headers: Dict[str, str] = None) -> HttpResponse:
        return self.__send_web_request(
            uri,
            HttpMethod.POST,
            body,
            response_on_error,
            headers
        )

    def __send_web_request(self, uri: str,
                           method: HttpMethod,
                           body: Union[str, Dict[str, Any]],
                           response_on_error=False,
                           headers: Dict[str, str] = None) -> HttpResponse:
        return self.sfdc_session.send_web_request(
            self.settings,
            method,
            uri,
            body,
            response_on_error=response_on_error,
            headers=headers)

    def __start_after_conversation_work(self, work_id: str):
        uri = self.build_presence_uri("StartAfterConversationWork")
        self.__post(
            uri,
            body={'workId': work_id}
        )

    def __invoke_conversation_request(self,
                                      action: str,
                                      body: Dict[str, Any]):
        uri = self.__build_conversation_uri(action)
        self.__post(
            uri,
            body=body
        )

    @staticmethod
    def __build_conversation_uri(action: str):
        return "rest/Conversational/" + action

    def close_work(self, work_target_id: str):
        work_id = self.work_id_repo.get_work_id(
            self.sfdc_session.tenant_id,
            self.sfdc_session.user_id,
            work_target_id
        )
        if not work_target_id.startswith('a17'):
            self.__end_conversation(work_target_id)
            self.__start_after_conversation_work(work_id)

        event_data = {
            'workId': work_id,
            'workTargetId': work_target_id
        }
        body = dict(event_data)
        body['activeTime'] = 1440
        self.__invoke_presence_request(
            "CloseWork",
            EventType.WORK_CLOSED,
            event_data,
            body
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

    def send_work_message(self, message: WorkMessage):
        # Yes, it's actually work target id we need to send here
        body = message.to_body(message.work_target_id)
        event_data = {'messageId': message.message_id}
        self.sfdc_session.send_web_request_with_event(
            EventType.MESSAGE_SENT,
            event_data,
            self.settings,
            HttpMethod.POST,
            "rest/Conversational/ConversationMessage",
            body,
            headers={
                'Accept': "*/*",
                'Content-Type': 'text/plain;charset=UTF-8'
            }
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        try:
            if self.settings != self.initial_settings:
                context = self.sfdc_context.set_session_data(self.settings.serialize())
                self.repo.update_session_context(context)
        finally:
            self.resource_lock.release()


@inject(bean_instances=(BeanName.RESOURCE_LOCK_REPO, BeanName.SESSION_CONTEXTS_REPO, BeanName.WORK_ID_MAP_REPO))
def load_api(
        session: Session,
        resource_lock_repo: ResourceLockRepo,
        contexts_repo: SessionContextsRepo,
        work_id_map_repo: WorkIdMapRepo
) -> OmniChannelApi:
    lock_name = f"web-session/{session.tenant_id}/{session.session_id}"
    lock, sc = resource_lock_repo.acquire_and_execute(lock_name, 1, 30,
                                                      lambda: load_with_context(session, ContextType.WEB))
    sc: SfdcSessionAndContext
    return lock.execute_and_release_on_exception(lambda:
                                                 _OmniChannelApi(sc.session,
                                                                 sc.context,
                                                                 lock,
                                                                 contexts_repo,
                                                                 work_id_map_repo))
