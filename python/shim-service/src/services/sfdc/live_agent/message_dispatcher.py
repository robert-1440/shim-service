from repos.session_push_notifications import SessionPushNotificationsRepo
from services.sfdc.live_agent.message_data import MessageData, Message
from session import SessionContext
from utils import loghelper

logger = loghelper.get_logger(__name__)

SUPPORTED_MESSAGE_TYPES = {
    'Agent/LoginResult',
    'Presence/PresenceStatusChanged',
    'Presence/WorkAssigned',
    'Presence/WorkAccepted',
    'Conversational/ConversationMessage',
    'LmAgent/ChatRequest',
    'LmAgent/ChatEstablished',
    'AsyncResult',
    'Presence/AfterConversationWorkStarted',
    'LiveAgentKitShutdown'
}

LOG_CALLBACK_TYPES = {
    'Presence/AcwExtensionProcessed',
    'Presence/AfterConversationWorkEnded',
    'Presence/AfterConversationWorkStarted',
    'Presence/EndAfterConversationWork',
    'Presence/FlagLowered',
    'Presence/AgentNotification',
    'Presence/FlagRaised',
    'Presence/PresenceConfiguration',
    'Presence/PresenceLogout',
    'Presence/PresenceSessionData',
    'Presence/WorkCanceled',
    'Presence/WorkClosed',
    'Presence/WorkForceClosed',
    'Presence/WorkTransferError',
    'Presence/WorkTransferred',
    'Presence/WorksReopenedOnLogin',
    'Conversational/AgentJoined',
    'Conversational/AgentLeft',
    'Conversational/ConferenceDeclined',
    'Conversational/ConversationEvent',
    'Conversational/ConversationEnded',
    'Conversational/ConversationDeliveryReceipt',
    'Conversational/ConferenceFailed',
    'Conversational/ConversationReassigned'
}


class LiveAgentMessageDispatcher:
    def __init__(self, push_notifier_repo: SessionPushNotificationsRepo):
        self.push_notifier_repo = push_notifier_repo

    def examine_message(self, context: SessionContext, message: Message):
        if message.type in SUPPORTED_MESSAGE_TYPES:
            self.push_notifier_repo.submit(
                context,
                context.context_type.to_platform_channel().name,
                message_type=message.type,
                message=message.message_text
            )
        else:
            note = "potential" if message.type in LOG_CALLBACK_TYPES else "other"
            logger.info(f"<<< {note}: {message.type} {message.message_text}")

    def dispatch_message_data(self, context: SessionContext, data: MessageData):
        message_set = set()

        def is_good(message: Message):
            if message not in message_set:
                message_set.add(message)
                return True
            return False

        for message in filter(is_good, data.messages):
            self.examine_message(context, message)
