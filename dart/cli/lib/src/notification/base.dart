import 'dart:convert';

import 'package:cli/src/channels.dart';
import 'package:cli/src/notification/event.dart';

class PushNotificationEvent {
  final PlatformChannelType channelType;

  final String messageType;

  final String message;

  final PollingEvent? pollingEvent;

  PushNotificationEvent(this.channelType, this.messageType, this.message) : pollingEvent = parseEvent(messageType, message);
}

PushNotificationEvent parsePushNotificationEvent(String message) {
  var map = jsonDecode(message);
  var payload = map['x1440Payload'];
  var newMap = jsonDecode(payload);
  return PushNotificationEvent(PlatformChannelType.valueOf(newMap['platformType']), newMap['messageType'], newMap['message']);
}
