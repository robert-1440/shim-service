import 'package:cli/src/notification/event.dart';

final workAssigned = EventType('Presence/WorkAssigned');
final presenceStatusChanged = EventType('Presence/PresenceStatusChanged');
final workAccepted = EventType('Presence/WorkAccepted');

class WorkAssignedEvent extends PollingEvent {
  late String workId;
  late String workTargetId;
  late String channelName;

  WorkAssignedEvent(Map<String, dynamic> eventData) : super(workAssigned) {
    workId = eventData['workId'];
    workTargetId = eventData['workTargetId'];
    channelName = eventData['channelName'];
  }

  @override
  Map<String, dynamic> toMap() {
    return {'workId': workId, 'workTargetId': workTargetId, 'channelName': channelName};
  }
}

class PresenceStatusChangedEvent extends PollingEvent {
  late String statusId;
  late String statusName;

  PresenceStatusChangedEvent(Map<String, dynamic> eventData) : super(presenceStatusChanged) {
    Map<String, dynamic> status = eventData['status'];
    statusId = status['statusId'];
    Map<String, dynamic> details = status['statusDetails'];
    statusName = details['statusName'];
  }

  @override
  Map<String, dynamic> toMap() {
    return {'statusId': statusId, 'statusName': statusName};
  }
}

class WorkAcceptedEvent extends PollingEvent {
  late String workId;

  WorkAcceptedEvent(Map<String, dynamic> eventData) : super(workAccepted) {
    workId = eventData['workId'];
  }

  @override
  Map<String, dynamic> toMap() {
    return {'workId': workId};
  }
}
