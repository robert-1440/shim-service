import 'package:cli/src/cli/util.dart';
import 'package:cli/src/notification/event.dart';

final loginResult = EventType("Agent/LoginResult");
final chatRequest = EventType("LmAgent/ChatRequest");
final chatEstablished = EventType("LmAgent/ChatEstablished");

class ChatMessage extends Mappable {
  final int sequence;
  final String content;
  final String entryType;

  ChatMessage(Map<String, dynamic> node)
      : sequence = node['sequence'],
        content = node['content'],
        entryType = node['entryType'];

  @override
  Map<String, dynamic> toMap() {
    return {'sequence': sequence, 'content': content, 'entryType': entryType};
  }

  @override
  String toString() {
    return "sequence=$sequence, content=$content, entryType=$entryType";
  }
}

class LoginResultEvent extends PollingEvent {
  late bool success;
  late String userName;
  late String userId;

  LoginResultEvent(Map<String, dynamic> eventData) : super(loginResult) {
    success = eventData['success'];
    Map<String, dynamic> userInfo = eventData['userInfo'];
    userName = userInfo['fullName'];
    userId = userInfo['id'];
  }

  @override
  String toString() {
    return "$eventType: success=$success, userName=$userName, userId=$userId";
  }

  @override
  Map<String, dynamic> toMap() {
    return {'success': success, 'userName': userName, 'userId': userId};
  }
}

class AbstractChatEvent extends PollingEvent {
  late String workTargetId;
  late List<ChatMessage> messages;

  AbstractChatEvent(super.eventType, Map<String, dynamic> eventData) {
    workTargetId = eventData['workTargetId'];
    messages = List<ChatMessage>.from(eventData['messages'].map((message) => ChatMessage(message)));
  }

  @override
  Map<String, dynamic> toMap() {
    return {'workTargetId': workTargetId, 'messages': messages.map((message) => message.toMap()).toList()};
  }
}

class ChatRequestEvent extends AbstractChatEvent {
  ChatRequestEvent(Map<String, dynamic> eventData) : super(chatRequest, eventData);
}

class ChatEstablishedEvent extends AbstractChatEvent {
  ChatEstablishedEvent(Map<String, dynamic> eventData) : super(chatEstablished, eventData);
}
