import abc
from copy import copy
from typing import List

from bean import BeanName
from bean.beans import inject
from repos.resource_lock import ResourceLock, ResourceLockRepo
from repos.session_contexts import SessionContextsRepo
from services.sfdc.live_agent import LiveAgentWebSettings, PresenceStatus
from services.sfdc.live_agent.api import presence_status
from services.sfdc.sfdc_session import SfdcSession, SfdcSessionAndContext, load_with_context
from session import Session, SessionContext, ContextType
from utils.http_client import HttpMethod


class OmniChannelApi(metaclass=abc.ABCMeta):

    @abc.abstractmethod
    def get_presence_statuses(self) -> List[PresenceStatus]:
        raise NotImplementedError()

    @abc.abstractmethod
    def set_presence_status(self, status: str):
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

    def get_presence_statuses(self) -> List[PresenceStatus]:
        return self.sfdc_session.get_presence_statuses()

    def set_presence_status(self, status_id: str):
        if len(status_id) == 0:
            resource_type = "Logout"
        else:
            resource_type = "Login"

        uri = "rest/Presence/Presence" + resource_type
        body = presence_status.construct_set_presence_status_body(self.sfdc_session, status_id)
        self.sfdc_session.send_web_request(self.settings, HttpMethod.POST, uri, body)

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
