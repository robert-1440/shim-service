import json

from mocks.extended_http_session_mock import ExtendedHttpMockSession
from services.sfdc.live_agent import LiveAgentStatus, LiveAgentSession, API_VERSION_STRING
from services.sfdc.live_agent.omnichannel import status_request_id, scrt_info_request_id, MESSAGE_RECORD
from services.sfdc.live_agent.scrt_info import ServiceChannelInfo, ScrtInfo
from support.http_support import decode_form_data
from test_salesforce_utils import AURA_TOKEN_STRING
from utils.http_client import HttpRequest
from utils.string_utils import uuid

ONLINE_ID = 'id1'
BUSY_ID = 'id2'
OFFLINE_ID = ''

SERVICE_CHANNELS = [
    ServiceChannelInfo(
        'channel1',
        'channel1-api-name',
        True,
        False,
        'related-1'
    ),
    ServiceChannelInfo(
        'channel2',
        'channel2-api-name',
        False,
        True,
        'related-2'
    ),
]

SCRT = ScrtInfo(
    acw_supported_entities_key_prefix=['hello', 'world'],
    has_live_agent=True,
    is_ci_allowed_to_user=True,
    service_channel_info=SERVICE_CHANNELS,
    has_record_action=True,
    has_auto_login_prompt=False,
    is_scv_allowed_to_user=True,
    has_scrt2_routing_connect_enabled=True,
    user_id="some-user",
    version=1,
    sfdc_session_key="sfdc-session_key",
    organization_id="org-id",
    end_point='https://somewhere.lightning.force.com/chat',
    has_lwc_transfer_component=True,
    content_end_point='some-content-endpoint',
    domain="some-domain",
    has_live_message=True,
    has_skills_based_routing=False,
    has_acw_allowed_perm=False,
    has_scrt2_conversation_perm=True,
    is_call_center_user=True

)

STATUSES = [
    LiveAgentStatus(
        ONLINE_ID,
        'Online',
        'css-online',
        True,
        False
    ),
    LiveAgentStatus(
        BUSY_ID,
        'Busy',
        'css-busy',
        False,
        False
    ),
    LiveAgentStatus(
        OFFLINE_ID,
        'Offline',
        'css-offline',
        False,
        True
    )

]

RESPONSE = {
    'actions': [
        {
            'id': status_request_id,
            'state': "SUCCESS",
            'returnValue': [item.to_record() for item in STATUSES]
        },
        {
            'id': scrt_info_request_id,
            'state': "SUCCESS",
            'returnValue': SCRT.to_record()
        }
    ]
}

_JSON_CONTENT = json.dumps(RESPONSE)

URL = "https://somewhere.lightning.force.com/aura?r=5&ui-liveagent-components-aura-controller.OmniWidget.getDeclineReasons=1&ui-liveagent-components-aura-controller.OmniWidget.getSCRTInfo=1&ui-liveagent-components-aura-controller.OmniWidget.getSoundInfo=1&ui-liveagent-components-aura-controller.OmniWidget.isBrowserNotificationEnabled=1&ui-liveagent-components-aura-controller.OmniWidget.isDeclineReasonEnabled=1&ui-liveagent-components-aura-controller.Status.getStatuses=1"

CHAT_URL = "https://somewhere-chat.lightning.force.com/chatter"

ACTUAL_CHAT_URL = "https://somewhere-chat.lightning.force.com/chat"

LIVE_AGENT_SESSION = LiveAgentSession(
    uuid(),
    uuid(),
    100,
    uuid()
)

LIVE_AGENT_SESSION_JSON = json.dumps(LIVE_AGENT_SESSION.to_record())

_EXPECTED_AURA_CONTEXT = {
    "fwuid": "this-is-the-framework-id",
    "mode": "?",
    "loaded": {"no": "clue"},
    "app": "app",
    "dn": [],
    "globals": {
        "appContextId": "app-context-id",
        "density": "some-density"
    },
    "uad": True
}


def __prepare_statuses_and_scrt_info(http_session_mock: ExtendedHttpMockSession, validate: bool):
    # Response for getting statuses and scrt info

    def callback(request: HttpRequest):
        decoded = decode_form_data(request.body)
        message_json = decoded['message']
        message = json.loads(message_json)
        assert message == MESSAGE_RECORD
        assert decoded['aura.pageURI'] == '/lightning'
        assert decoded['aura.token'] == AURA_TOKEN_STRING

    http_session_mock.add_post_response(
        URL,
        200,
        body=_JSON_CONTENT,
        expected_content_type='application/x-www-form-urlencoded',
        request_callback=callback if validate else None
    )


def prepare_live_agent(http_session_mock: ExtendedHttpMockSession, validate: bool = False):
    __prepare_statuses_and_scrt_info(http_session_mock, validate)

    http_session_mock.add_get_response(
        'https://somewhere.lightning.force.com/chat/rest/cdm?version=58&redirect=true',
        301,
        headers={
            'location': CHAT_URL
        }
    )

    http_session_mock.add_get_response(
        'https://somewhere-chat.lightning.force.com/chat/rest/System/SessionId?SessionId.ClientType=lightning',
        200,
        body=LIVE_AGENT_SESSION_JSON,
        expected_headers={
            'X-Liveagent-Affinity': 'null',
            'X-Liveagent-Api-Version': API_VERSION_STRING
        }
    )
