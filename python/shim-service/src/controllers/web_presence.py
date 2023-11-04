from controllers import ROOT
from lambda_web_framework.request import LambdaHttpRequest, from_json, get_required_parameter, assert_empty, \
    LambdaHttpResponse
from lambda_web_framework.resource import Resource
from lambda_web_framework.web_exceptions import InvalidParameterException
from lambda_web_framework.web_router import Method
from services.sfdc.live_agent.omnichannel_api import OmniChannelApi
from utils import collection_utils

presence = Resource(ROOT, "presence-statuses")


class SetPresenceBody:
    def __init__(self, request: LambdaHttpRequest):
        record = from_json(request.body)
        status_id = get_required_parameter(record, "id", str, remove=True, empty_ok=True)
        assert_empty(record)

        self.status_id: str = status_id


@presence.route("",
                response_codes=(200,),
                api_required=True,
                no_instance=True,
                body_transformer=SetPresenceBody,
                method=Method.POST)
def set_presence_status(status_body: SetPresenceBody, api: OmniChannelApi):
    statuses = api.get_presence_statuses()
    match = collection_utils.find_first_match(statuses, lambda m: m.id == status_body.status_id)
    if match is None:
        raise InvalidParameterException("id", f"'{status_body.status_id}' is invalid.")

    api.set_presence_status(status_body.status_id)
    return LambdaHttpResponse.ok()
