from typing import Any, Dict

from services.sfdc.sfdc_session import SfdcSession

CHANNEL_IDS_WITH_PARAM = [
    {'channelId': 'agent'},
    {'channelId': 'conversational'},
    {'channelId': 'lmagent'},  # WE NEED THIS FOR SMS!!!! // TODO: get these dynamically
]


def construct_set_presence_status_body(sfdc_session: SfdcSession,
                                       status_id: str) -> Dict[str, Any]:
    body = {
        'organizationId': sfdc_session.organization_id,
        'sfdcSessionId': sfdc_session.get_lightning_session_id(),
        'statusId': status_id,
        'channelIdsWithParam': CHANNEL_IDS_WITH_PARAM,
        'domain': sfdc_session.lightning_domain
    }
    return body
