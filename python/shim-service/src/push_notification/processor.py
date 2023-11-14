import json
from typing import Dict, Any

from bean import InvocableBean
from lambda_pkg.functions import LambdaFunction
from push_notification import PushNotificationContextSettings, SessionPushNotification
from push_notification.manager import PushNotificationManager
from repos.resource_lock import session_try_auto_lock, SessionLockedException
from repos.session_contexts import SessionContextsRepo, SessionContextAndFcmToken
from repos.session_push_notifications import SessionPushNotificationsRepo
from session import ContextType, SessionKey
from utils import loghelper, date_utils

logger = loghelper.get_logger(__name__)


class PushNotificationProcessor(InvocableBean):

    def __init__(self, session_contexts_repo: SessionContextsRepo,
                 push_notification_repo: SessionPushNotificationsRepo,
                 push_notifier: PushNotificationManager):
        self.session_contexts_repo = session_contexts_repo
        self.push_notification_repo = push_notification_repo
        self.push_notifier = push_notifier

    def __notify(self, entry: SessionContextAndFcmToken,
                 settings: PushNotificationContextSettings,
                 record: SessionPushNotification) -> bool:
        try:
            payload = {
                'platformType': record.platform_channel_type,
                'messageType': record.message_type,
                'message': record.message
            }

            data = {
                'x1440Payload': json.dumps(payload)
            }
            self.push_notifier.send_push_notification(entry.token, data)
            settings.last_seq_no = record.seq_no
            new_context = entry.context.set_session_data(settings.serialize())
            self.push_notification_repo.set_sent(record, new_context)
            entry.context = new_context
            return True
        except BaseException as ex:
            logger.severe(f"Error processing notification seq_no {record.seq_no}", ex=ex)

        return False

    def __process_record(self, settings: PushNotificationContextSettings,
                         entry: SessionContextAndFcmToken,
                         record: SessionPushNotification):
        logger.info(f"Processing notification: channelType={record.platform_channel_type}, "
                    f"messageType={record.message_type}, "
                    f"created={date_utils.millis_to_timestamp(record.time_created)}")

        if not self.__notify(entry, settings, record):
            return False

        return True

    @session_try_auto_lock("push-notifier", refresh_seconds=30, lambda_function=LambdaFunction.PushNotifier)
    def __process(self, entry: SessionContextAndFcmToken):
        logger.info("Checking for push notification entries...")
        count = 0
        ctx = entry.context
        settings = PushNotificationContextSettings.deserialize(ctx.session_data)
        result_set = self.push_notification_repo.query_notifications(ctx, settings.last_seq_no)
        for record in result_set:
            if not self.__process_record(settings, entry, record):
                break
            count += 1

        logger.info(f"Total number notifications sent: {count}.")

    def invoke(self, parameters: Dict[str, Any]):
        session_key = SessionKey.key_from_dict(parameters)
        entry: SessionContextAndFcmToken = self.session_contexts_repo.find_session_context_with_fcm_token(session_key,
                                                                                                          ContextType.PUSH_NOTIFIER)
        if entry is None:
            logger.info(f"Context for {session_key} does not exist.")
            return

        if entry.token is None:
            logger.info(f"FCM device token for {session_key} is empty, deleting context.")
            self.session_contexts_repo.delete_session_context(session_key, entry.context.context_type)
            return

        try:
            session_key.execute_with_logging(lambda: self.__process(entry))
        except SessionLockedException:
            logger.info(f"Session {session_key} is locked.")
