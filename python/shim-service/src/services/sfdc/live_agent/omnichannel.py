import json
from typing import Tuple, List, Optional

from services.sfdc.live_agent import LiveAgentStatus
from services.sfdc.live_agent.scrt_info import ScrtInfo
from services.sfdc.types.aura_context import AuraSettings
from utils import loghelper
from utils.http_client import HttpClient, MediaType
from utils.http_utils import Raw, encode_form_data
from utils.uri_utils import encode_query_component

logger = loghelper.get_logger(__name__)

status_request_id = '512;a'
browser_notification_enabled_request_id = '554;a'
scrt_info_request_id = '5744;a'
is_decline_reason_enabled_request_id = '556;a'
declineReasonsRequestId = '557;a'
sound_info_request_id = '558;a'

MESSAGE_RECORD = {
    "actions": [
        {
            "id": status_request_id,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.StatusController/ACTION$getStatuses",
            "callingDescriptor": "UNKNOWN",
            "params": {}
        },
        {
            "id": browser_notification_enabled_request_id,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.OmniWidgetController/ACTION$isBrowserNotificationEnabled",
            "callingDescriptor": "UNKNOWN",
            "params": {}
        },
        {
            "id": scrt_info_request_id,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.OmniWidgetController/ACTION$getSCRTInfo",
            "callingDescriptor": "UNKNOWN",
            "params": {}
        },
        {
            "id": is_decline_reason_enabled_request_id,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.OmniWidgetController/ACTION$isDeclineReasonEnabled",
            "callingDescriptor": "UNKNOWN",
            "params": {}
        },
        {
            "id": declineReasonsRequestId,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.OmniWidgetController/ACTION$getDeclineReasons",
            "callingDescriptor": "UNKNOWN",
            "params": {}
        },
        {
            "id": sound_info_request_id,
            "descriptor": "serviceComponent://ui.liveagent.components.aura.controller.OmniWidgetController/ACTION$getSoundInfo",
            "callingDescriptor": "UNKNOWN",
            "params": {"id": "", "isServiceChannel": False}
        }
    ]
}

_MESSAGE_BODY = Raw(encode_query_component(json.dumps(MESSAGE_RECORD)))
_PAGE_URI = Raw('%2Flightning')


def get_statuses_and_scrt_info(settings: AuraSettings,
                               domain: str,
                               client: HttpClient) -> Tuple[List[LiveAgentStatus], Optional[ScrtInfo]]:
    url = f'https://{domain}/aura?r=5&ui-liveagent-components-aura-controller.OmniWidget.getDeclineReasons=1&ui-liveagent-components-aura-controller.OmniWidget.getSCRTInfo=1&ui-liveagent-components-aura-controller.OmniWidget.getSoundInfo=1&ui-liveagent-components-aura-controller.OmniWidget.isBrowserNotificationEnabled=1&ui-liveagent-components-aura-controller.OmniWidget.isDeclineReasonEnabled=1&ui-liveagent-components-aura-controller.Status.getStatuses=1'
    params = {
        'message': _MESSAGE_BODY,
        'aura.context': settings.to_json(),
        'aura.pageURI': _PAGE_URI,
        'aura.token': settings.aura_token
    }

    resp = client.post(url, MediaType.X_WWW_FORM_URLENCODED, accept_type=MediaType.JSON,
                       body=encode_form_data(params))

    record = json.loads(resp.body)
    actions_list = record['actions']
    status_options_result = next((action for action in actions_list if action['id'] == status_request_id), None)

    if status_options_result and status_options_result['state'] == 'SUCCESS':
        live_agent_status_options = [LiveAgentStatus.from_record(e) for e in
                                     status_options_result['returnValue']]
    else:
        live_agent_status_options = []

    scrt_info_json = next((action for action in actions_list if action['id'] == scrt_info_request_id), None)
    if scrt_info_json:
        scrt_info = ScrtInfo.from_record(scrt_info_json['returnValue'])
    else:
        scrt_info = None
    return live_agent_status_options, scrt_info
