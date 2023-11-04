from typing import List

from controllers import ROOT
from instance import Instance
from lambda_web_framework.request import from_json, get_required_parameter, assert_empty, LambdaHttpRequest, \
    LambdaHttpResponse
from lambda_web_framework.resource import Resource
from lambda_web_framework.web_exceptions import LambdaHttpException, \
    GoneException, BadRequestException
from lambda_web_framework.web_router import Method
from platform_channels import assert_valid_platform_channel
from repos.sessions_repo import UserSessionExistsException
from session import manager, SessionToken, Session
from utils import validation_utils
from utils.date_utils import get_system_time_in_millis
from utils.string_utils import uuid
from utils.validation_utils import get_tenant_id

sessions = Resource(ROOT, "organizations/{orgId}/sessions")


def _extract_platform_channel_types(source: List[str]) -> List[str]:
    if len(source) == 0:
        raise BadRequestException("Need at least one channelPlatformType.")
    this_set = set(source)
    return list(filter(assert_valid_platform_channel, this_set))


def __build_session(instance: Instance, request: LambdaHttpRequest, org_id: str) -> Session:
    body = from_json(request.body)
    user_id = validation_utils.get_user_id(body)
    instance_url = validation_utils.get_url(body, 'instanceUrl')
    fcm_device_token = get_required_parameter(body, "fcmDeviceToken", str, remove=True,
                                              max_length=2048)
    access_token = get_required_parameter(body, 'accessToken', str, remove=True, max_length=4096)
    platform_channels = _extract_platform_channel_types(
        get_required_parameter(body, 'channelPlatformTypes', list, remove=True))

    assert_empty(body)

    tenant_id = get_tenant_id(instance, request, org_id)
    session = Session(
        tenant_id=tenant_id,
        session_id=uuid(),
        time_created=get_system_time_in_millis(),
        user_id=user_id,
        instance_url=instance_url,
        access_token=access_token,
        fcm_device_token=fcm_device_token,
        expiration_seconds=instance.config.session_expiration_seconds,
        channel_platform_types=platform_channels)
    return session


@sessions.route("",
                response_codes=(200, 201),
                method=Method.POST)
def start_session(instance: Instance, request: LambdaHttpRequest, orgId: str):
    creds = request.get_credentials()
    session = __build_session(instance, request, orgId)
    async_request = request.get_header('Prefer') == 'respond-async'
    try:
        result = manager.create_session(session, async_request)
    except UserSessionExistsException as ex:
        token = SessionToken(session.tenant_id, ex.session_id, session.user_id).serialize(creds)
        raise LambdaHttpException(409, "User is logged into another session.",
                                  headers={'X-1440-Session-Token': token})
    except Exception as ex:
        raise ex

    session = result.session
    token = SessionToken(session.tenant_id, session.session_id, session.user_id)

    token_string = token.serialize(creds)
    if result.created:
        code = 202 if async_request else 201
    else:
        code = 200
    return LambdaHttpResponse(code, {'sessionToken': token_string})


@sessions.route("{sessionToken}/actions/keep-alive",
                response_codes=(204,),
                include_request=True,
                method=Method.POST)
def keepalive(instance: Instance, request: LambdaHttpRequest, orgId: str, sessionToken: str):
    get_tenant_id(instance, request, orgId)
    expiration_time = manager.keepalive(sessionToken, request)
    return LambdaHttpResponse.ok({"expirationTime": expiration_time})


@sessions.route("{sessionToken}",
                response_codes=(204, 410),
                include_request=True,
                method=Method.DELETE)
def end_session(instance: Instance, request: LambdaHttpRequest, orgId: str, sessionToken: str):
    get_tenant_id(instance, request, orgId)

    if not manager.delete_session_by_token(sessionToken, request):
        raise GoneException("Session no longer exists.")
    return LambdaHttpResponse.no_content()
