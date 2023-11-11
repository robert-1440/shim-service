import 'dart:convert';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/notification/events/agent.dart';
import 'package:cli/src/notification/events/conversational.dart';
import 'package:cli/src/notification/events/misc.dart';
import 'package:cli/src/notification/events/presence.dart';

typedef EventFactory = PollingEvent Function(Map<String, dynamic> map);

class EventType {
  final String name;

  EventType(this.name);

  @override
  bool operator ==(Object other) {
    return other is EventType && other.name == name;
  }

  @override
  int get hashCode => name.hashCode;

  @override
  String toString() {
    return name;
  }
}

class EventBuilder {
  final EventType eventType;

  final EventFactory factory;

  EventBuilder(this.eventType, this.factory);
}

final _eventBuilders = [
  EventBuilder(loginResult, (map) => LoginResultEvent(map)),
  EventBuilder(chatRequest, (map) => ChatRequestEvent(map)),
  EventBuilder(chatEstablished, (map) => ChatEstablishedEvent(map)),
  EventBuilder(workAssigned, (map) => WorkAssignedEvent(map)),
  EventBuilder(presenceStatusChanged, (map) => PresenceStatusChangedEvent(map)),
  EventBuilder(workAccepted, (map) => WorkAcceptedEvent(map)),
  EventBuilder(conversationMessage, (map) => ConversationMessageEvent(map)),
  EventBuilder(asyncResult, (map) => AsyncResultEvent(map))
];

final _eventBuildersMap = Map.fromEntries(_eventBuilders.map((builder) => MapEntry(builder.eventType.name, builder)));

abstract class PollingEvent extends Mappable {
  final EventType eventType;

  PollingEvent(this.eventType);
}

PollingEvent? parseEvent(String messageType, String message) {
  final builder = _eventBuildersMap[messageType];
  if (builder == null) {
    return null;
  }
  Map<String, dynamic> map;
  try {
    map = jsonDecode(message);
  } catch (_) {
    return null;
  }

  return builder.factory(map);
}
