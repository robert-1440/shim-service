from typing import List, Optional


class ServiceChannelInfo:
    def __init__(self,
                 channel_id: Optional[str],
                 channel_api_name: Optional[str],
                 does_minimize_on_accept: Optional[bool],
                 has_auto_accept_enabled: Optional[bool],
                 related_entity: Optional[str]):
        self.channel_id = channel_id
        self.channel_api_name = channel_api_name
        self.does_minimize_on_accept = does_minimize_on_accept
        self.has_auto_accept_enabled = has_auto_accept_enabled
        self.related_entity = related_entity

    def to_record(self) -> dict:
        return {
            'channelId': self.channel_id,
            'channelApiName': self.channel_api_name,
            'doesMinimizeOnAccept': self.does_minimize_on_accept,
            'hasAutoAcceptEnabled': self.has_auto_accept_enabled,
            'relatedEntity': self.related_entity
        }

    def __eq__(self, other):
        if not isinstance(other, ServiceChannelInfo):
            return False

        return (
                self.channel_id == other.channel_id and
                self.channel_api_name == other.channel_api_name and
                self.does_minimize_on_accept == other.does_minimize_on_accept and
                self.has_auto_accept_enabled == other.has_auto_accept_enabled and
                self.related_entity == other.related_entity
        )

    @classmethod
    def from_record(cls, record):
        return cls(
            record['channelId'],
            record['channelApiName'],
            record['doesMinimizeOnAccept'],
            record['hasAutoAcceptEnabled'],
            record['relatedEntity']
        )


class ScrtInfo:
    def __init__(self,
                 acw_supported_entities_key_prefix: Optional[List[str]],
                 has_live_agent: Optional[bool],
                 is_ci_allowed_to_user: Optional[bool],
                 service_channel_info: Optional[List[ServiceChannelInfo]],
                 has_record_action: Optional[bool],
                 has_auto_login_prompt: Optional[bool],
                 is_scv_allowed_to_user: Optional[bool],
                 has_scrt2_routing_connect_enabled: Optional[bool],
                 user_id: Optional[str],
                 version: Optional[int],
                 sfdc_session_key: Optional[str],
                 organization_id: Optional[str],
                 end_point: Optional[str],
                 has_lwc_transfer_component: Optional[bool],
                 content_end_point: Optional[str],
                 domain: Optional[str],
                 has_live_message: Optional[bool],
                 has_skills_based_routing: Optional[bool],
                 has_acw_allowed_perm: Optional[bool],
                 has_scrt2_conversation_perm: Optional[bool],
                 is_call_center_user: Optional[bool]):
        self.acw_supported_entities_key_prefix = acw_supported_entities_key_prefix
        self.has_live_agent = has_live_agent
        self.is_ci_allowed_to_user = is_ci_allowed_to_user
        self.service_channel_info: List[ServiceChannelInfo] = service_channel_info
        self.has_record_action = has_record_action
        self.has_auto_login_prompt = has_auto_login_prompt
        self.is_scv_allowed_to_user = is_scv_allowed_to_user
        self.has_scrt2_routing_connect_enabled = has_scrt2_routing_connect_enabled
        self.user_id = user_id
        self.version = version
        self.sfdc_session_key = sfdc_session_key
        self.organization_id = organization_id
        self.end_point = end_point
        self.has_lwc_transfer_component = has_lwc_transfer_component
        self.content_end_point = content_end_point
        self.domain = domain
        self.has_live_message = has_live_message
        self.has_skills_based_routing = has_skills_based_routing
        self.has_acw_allowed_perm = has_acw_allowed_perm
        self.has_scrt2_conversation_perm = has_scrt2_conversation_perm
        self.is_call_center_user = is_call_center_user

    def to_record(self) -> dict:
        return {
            'acwSupportedEntitiesKeyPrefix': self.acw_supported_entities_key_prefix,
            'hasLiveAgent': self.has_live_agent,
            'isCIAllowedToUser': self.is_ci_allowed_to_user,
            'serviceChannelInfo': [item.to_record() for item in self.service_channel_info],
            'hasRecordAction': self.has_record_action,
            'hasAutoLoginPrompt': self.has_auto_login_prompt,
            'isSCVAllowedToUser': self.is_scv_allowed_to_user,
            'hasScrt2RoutingConnectEnabled': self.has_scrt2_routing_connect_enabled,
            'userId': self.user_id,
            'version': self.version,
            'sfdcSessionKey': self.sfdc_session_key,
            'organizationId': self.organization_id,
            'endPoint': self.end_point,
            'hasLwcTransferComponent': self.has_lwc_transfer_component,
            'contentEndPoint': self.content_end_point,
            'domain': self.domain,
            'hasLiveMessage': self.has_live_message,
            'hasSkillsBasedRouting': self.has_skills_based_routing,
            'hasACWAllowedPerm': self.has_acw_allowed_perm,
            'hasScrt2ConversationPerm': self.has_scrt2_conversation_perm,
            'isCallCenterUser': self.is_call_center_user
        }

    def __eq__(self, other):
        if not isinstance(other, ScrtInfo):
            return False

        return (
                self.acw_supported_entities_key_prefix == other.acw_supported_entities_key_prefix and
                self.has_live_agent == other.has_live_agent and
                self.is_ci_allowed_to_user == other.is_ci_allowed_to_user and
                self.service_channel_info == other.service_channel_info and
                self.has_record_action == other.has_record_action and
                self.has_auto_login_prompt == other.has_auto_login_prompt and
                self.is_scv_allowed_to_user == other.is_scv_allowed_to_user and
                self.has_scrt2_routing_connect_enabled == other.has_scrt2_routing_connect_enabled and
                self.user_id == other.user_id and
                self.version == other.version and
                self.sfdc_session_key == other.sfdc_session_key and
                self.organization_id == other.organization_id and
                self.end_point == other.end_point and
                self.has_lwc_transfer_component == other.has_lwc_transfer_component and
                self.content_end_point == other.content_end_point and
                self.domain == other.domain and
                self.has_live_message == other.has_live_message and
                self.has_skills_based_routing == other.has_skills_based_routing and
                self.has_acw_allowed_perm == other.has_acw_allowed_perm and
                self.has_scrt2_conversation_perm == other.has_scrt2_conversation_perm and
                self.is_call_center_user == other.is_call_center_user
        )

    @classmethod
    def from_record(cls, record):
        acw_supported_entities_key_prefix = record.get('acwSupportedEntitiesKeyPrefix', [])
        service_channel_info = [ServiceChannelInfo.from_record(item) for item in record.get('serviceChannelInfo', [])]
        return cls(
            acw_supported_entities_key_prefix,
            record['hasLiveAgent'],
            record['isCIAllowedToUser'],
            service_channel_info,
            record['hasRecordAction'],
            record['hasAutoLoginPrompt'],
            record['isSCVAllowedToUser'],
            record['hasScrt2RoutingConnectEnabled'],
            record['userId'],
            record['version'],
            record['sfdcSessionKey'],
            record['organizationId'],
            record['endPoint'],
            record['hasLwcTransferComponent'],
            record['contentEndPoint'],
            record['domain'],
            record['hasLiveMessage'],
            record['hasSkillsBasedRouting'],
            record['hasACWAllowedPerm'],
            record['hasScrt2ConversationPerm'],
            record['isCallCenterUser']
        )
