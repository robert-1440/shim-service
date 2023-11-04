from controllers import ROOT
from lambda_web_framework.request import LambdaHttpRequest, from_json, get_required_parameter, assert_empty, \
    LambdaHttpResponse
from lambda_web_framework.resource import Resource
from lambda_web_framework.web_exceptions import InvalidParameterException
from lambda_web_framework.web_router import Method
from services.sfdc.live_agent.omnichannel_api import OmniChannelApi
from utils import collection_utils
from utils.validation_utils import get_work_id, get_work_target_id

presence = Resource(ROOT, "")


class SetPresenceBody:
    def __init__(self, request: LambdaHttpRequest):
        record = from_json(request.body)
        status_id = get_required_parameter(record, "id", str, remove=True, empty_ok=True)
        assert_empty(record)

        self.status_id: str = status_id


@presence.route("presence-statuses",
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


class AcceptWorkBody:
    def __init__(self, request: LambdaHttpRequest):
        record = from_json(request.body)
        self.work_id = get_work_id(record)
        self.work_target_id = get_work_target_id(record)
        assert_empty(record)


@presence.route("presence/actions/accept-work",
                response_codes=(200,),
                api_required=True,
                no_instance=True,
                body_transformer=AcceptWorkBody,
                method=Method.POST)
def accept_work(work_body: AcceptWorkBody, api: OmniChannelApi):
    api.accept_work(work_body.work_id, work_body.work_target_id)
    return LambdaHttpResponse.ok()
