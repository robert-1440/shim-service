import 'package:cli/src/notification/event.dart';

final conversationMessage = EventType('Conversational/ConversationMessage');

class ConversationMessageEvent extends PollingEvent {
  late String text;
  late List<dynamic> attachments;
  late String workId;

  ConversationMessageEvent(Map<String, dynamic> eventData) : super(conversationMessage) {
    text = eventData['text'];
    attachments = eventData['attachments'];
    workId = eventData['workId'];
  }

  @override
  String toString() {
    return "$eventType: text=$text, attachments=$attachments, workId=$workId";
  }

  @override
  Map<String, dynamic> toMap() {
    return {
      'text': text,
      'attachments': attachments,
      'workId': workId
    };
  }
}
