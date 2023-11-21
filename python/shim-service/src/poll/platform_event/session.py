from typing import List, Optional

from bean import inject, BeanName
from repos.sessions_repo import SessionsRepo
from utils import loghelper

logger = loghelper.get_logger(__name__)


class PlatformEventSession:

    def __init__(self, tenant_id: int, access_token: str):
        self.tenant = tenant_id
        self.access_token = access_token

    def poll(self):
        pass


@inject(bean_instances=BeanName.SESSIONS_REPO)
def create_platform_event_session(tenant_id: int, sessions_repo: SessionsRepo) -> Optional[PlatformEventSession]:
    access_token = sessions_repo.find_most_recent_access_token(tenant_id)
    return PlatformEventSession(tenant_id, access_token) if access_token is not None else None
