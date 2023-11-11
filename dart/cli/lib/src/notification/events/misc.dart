import 'package:cli/src/notification/event.dart';

final asyncResult = EventType("AsyncResult");

class AsyncResultEvent extends PollingEvent {
  late int sequence;
  late bool success;

  AsyncResultEvent(Map<String, dynamic> eventData) : super(asyncResult) {
    sequence = eventData['sequence'];
    success = eventData['isSuccess'];
  }

  @override
  Map<String, dynamic> toMap() {
    return {
      'sequence': sequence,
      'success': success
    };
  }
}
