import os

import bean
from bean.profiles import describe_profiles, ALL_PROFILES

os.environ['ACTIVE_PROFILES'] = describe_profiles(ALL_PROFILES)

from bean import InvocableBean, BeanName
from manual import setup
from manual.event_handler import OurEventListener
from pending_event import PendingEventType
from platform_channels import OMNI_PLATFORM, X1440_PLATFORM
from repos.pending_event_repo import PendingEventsRepo
from services.sfdc import SfdcAuthenticator
from services.sfdc.live_agent.omnichannel_api import OmniChannelApi, load_api
from session import Session
from session.manager import CreateResult, create_session
from support import salesforce_auth, thread_utils
from support.salesforce_auth import AuthInfo
from utils.uri_utils import Uri


def poll():
    poller: InvocableBean = bean.get_bean_instance(BeanName.LIVE_AGENT_PROCESSOR)
    pe_repo: PendingEventsRepo = bean.get_bean_instance(BeanName.PENDING_EVENTS_REPO)
    event = {}
    while True:
        events = pe_repo.query_events(PendingEventType.LIVE_AGENT_POLL, 1)
        if len(events.rows) < 1:
            break
        poller.invoke(event)


class _SfdcAuthenticatorImpl(SfdcAuthenticator):
    def __init__(self, auth_info: AuthInfo, session: Session):
        super(_SfdcAuthenticatorImpl, self).__init__(session)
        self.auth_info = auth_info

    def get_access_token(self) -> str:
        return self.auth_info.session_id


our_listener = OurEventListener()

setup.init(our_listener)

auth_info = salesforce_auth.get_auth_info()
uri = Uri.parse(auth_info.server_url).origin

session = Session("some-org-id",1000, 'my-session-id', None, auth_info.user_id, instance_url=uri,
                  access_token=auth_info.session_id,
                  fcm_device_token="skip::this-is-a-token", expiration_seconds=3600,
                  channel_platform_types=[OMNI_PLATFORM.name, X1440_PLATFORM.name])

result: CreateResult = create_session(session, False)
sess = result.session
t = thread_utils.start_thread(poll)

t.join(3)

api: OmniChannelApi = load_api(sess)
our_listener.set_online(api)

t.join()
