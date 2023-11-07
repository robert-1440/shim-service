from enum import Enum
from typing import Optional

from platform_channels import PlatformChannel


class ChannelProvider(Enum):
    SALESFORCE = 0
    MESSAGING_STUDIO = 1
    AWS = 2


class ParticipantType(Enum):
    EMPLOYEE = 0
    VISITOR = 1
    BOT = 2


class Participant:
    def __init__(self,
                 contact_id: str,
                 photo_url: str,
                 email: str,
                 name: str,
                 home_phone: str,
                 owner_full_photo_url: str):
        self.contact_id = contact_id
        self.photo_url = photo_url
        self.email = email
        self.name = name
        self.home_phone = home_phone
        self.owner_full_photo_url = owner_full_photo_url


class Conversation:

    def __init__(self,
                 tenant_id: int,
                 external_conversation_id: str,
                 conversation_id: str,
                 channel_type: str,
                 owner_id: str,
                 messaging_session_id: Optional[str],
                 contact: Optional[Participant],
                 status: str,
                 work_id: Optional[str],
                 target_work_id: Optional[str]):
        self.tenant_id = tenant_id
        self.external_conversation_id = external_conversation_id
        self.conversation_id = conversation_id
        self.channel_type = channel_type
        self.owner_id = owner_id
        self.messaging_session_id = messaging_session_id
        self.contact = contact
        self.status = status
        self.work_id = work_id
        self.target_work_id = target_work_id

