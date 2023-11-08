from typing import Optional, Dict, Any, List

from controllers import ROOT
from lambda_web_framework.request import LambdaHttpRequest, get_required_parameter, from_json, get_parameter, \
    LambdaHttpResponse, assert_empty
from lambda_web_framework.resource import Resource
from lambda_web_framework.web_exceptions import InvalidParameterException, BadRequestException
from lambda_web_framework.web_router import Method
from services.sfdc.live_agent.omnichannel_api import OmniChannelApi, MessageAttachment, WorkMessage
from utils.validation_utils import validate_work_target_id

conversations = Resource(ROOT, "")


def _transform_attachments(attachment_list: Optional[List[Dict[str, Any]]]) -> Optional[List[MessageAttachment]]:
    if attachment_list is None:
        return None
    results = []
    index = 0
    for a in attachment_list:
        if type(a) is not dict:
            error_text = "invalid type."
        else:
            key = a.get('key')
            if key is None:
                error_text = "Missing 'key'."
            elif type(key) is not str:
                error_text = "'key' must be a string."
            else:
                value = a.get('value')
                if value is None:
                    error_text = "Missing 'value'."
                elif type(value) is not str:
                    error_text = "'value' must be a string."
                else:
                    error_text = None
                    results.append(MessageAttachment(key, value))
        if error_text is not None:
            raise InvalidParameterException(f'attachments[{index}]', error_text)
        index += 1

    return results if len(results) > 0 else None


class MessageBody:
    def __init__(self, request: LambdaHttpRequest):
        self.work_target_id = request.get_url_parameter("workTargetId")
        validate_work_target_id(self.work_target_id, in_path=True)
        body = from_json(request.body)
        self.message_id = get_required_parameter(body, "id", str, remove=True)
        self.message_body = get_parameter(body, "messageBody", str, remove=True, none_if_empty=True)
        self.attachments = _transform_attachments(get_parameter(body, "attachments", list, remove=True))

        assert_empty(body)

        if self.message_body is None and self.attachments is None:
            raise BadRequestException("Either messageBody or attachments must be specified.")


@conversations.route("work-conversations/{workTargetId}/messages",
                     response_codes=(204,),
                     api_required=True,
                     no_instance=True,
                     body_transformer=MessageBody,
                     method=Method.POST)
def send_work_message(body: MessageBody, api: OmniChannelApi):
    message = WorkMessage(
        body.work_target_id,
        body.message_id,
        body.message_body,
        body.attachments
    )
    api.send_work_message(message)
    return LambdaHttpResponse.no_content()
