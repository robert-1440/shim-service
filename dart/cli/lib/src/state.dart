import 'dart:convert';
import 'dart:io';

import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/client/support/session.dart';
import 'package:cli/src/notification/base.dart';
import 'package:cli/src/notification/event.dart';
import 'package:cli/src/notification/events/agent.dart';
import 'package:cli/src/notification/events/conversational.dart';
import 'package:cli/src/notification/events/presence.dart';

typedef EventMapper = void Function(SessionState state, PollingEvent event);

final Map<EventType, EventMapper> mapper = {
  loginResult: (state, event) => state._loginResult(event as LoginResultEvent),
  presenceStatusChanged: (state, event) => state._presenceStatusChanged(event as PresenceStatusChangedEvent),
  workAssigned: (state, event) => state._workAssigned(event as WorkAssignedEvent),
  workAccepted: (state, event) => state._workAccepted(event as WorkAcceptedEvent),
  chatEstablished: (state, event) => state._chatEstablished(event as ChatEstablishedEvent),
  chatRequest: (state, event) => state._chatRequest(event as ChatRequestEvent),
  conversationMessage: (state, event) => state._conversationMessage(event as ConversationMessageEvent),
};

class WorkAssignment extends Mappable {
  final String workId;

  final String workTargetId;

  final String channelName;

  WorkAssignment(this.workId, this.workTargetId, this.channelName);

  @override
  operator ==(Object other) {
    if (other is WorkAssignment) {
      return workId == other.workId && workTargetId == other.workTargetId && channelName == other.channelName;
    }
    return false;
  }

  @override
  int get hashCode => workId.hashCode ^ workTargetId.hashCode ^ channelName.hashCode;

  @override
  toMap() {
    return {"workId": workId, "workTargetId": workTargetId, "channelName": channelName};
  }

  @override
  String toString() {
    return "workId: $workId, workTargetId: $workTargetId, channelName: $channelName";
  }

  factory WorkAssignment.fromMap(Map<String, dynamic> map) {
    return WorkAssignment(map['workId'], map['workTargetId'], map['channelName']);
  }
}

class SessionState extends Mappable {
  final String orgId;

  final String token;

  final List<PresenceStatus> presenceStatuses;

  late File _file;

  bool _loggedIn = false;

  String? _userName;

  String? _presenceStatus;

  List<WorkAssignment> _workAssignments = [];

  List<String> _acceptedWorkIds = [];

  List<ChatMessage> _chatMessages = [];

  List<ConversationMessageEvent> _conversationMessages = [];

  SessionState(this.orgId, [this.token = "", this.presenceStatuses = const []]);

  @override
  Map<String, dynamic> toMap() {
    return {
      'orgId': orgId,
      'token': token,
      'presenceStatuses': presenceStatuses.map((status) => status.toMap()).toList(),
      "loggedIn": _loggedIn,
      "userName": _userName,
      "presenceStatus": _presenceStatus,
      "workAssignments": _workAssignments.map((assignment) => assignment.toMap()).toList(),
      "acceptedWorkIds": _acceptedWorkIds,
      "chatMessages": _chatMessages.map((message) => message.toMap()).toList(),
      "conversationMessages": _conversationMessages.map((message) => message.toMap()).toList(),
    };
  }

  String? get userName => _userName;

  void _loginResult(LoginResultEvent event) {
    _loggedIn = event.success;
    _userName = event.userName;
  }

  void _presenceStatusChanged(PresenceStatusChangedEvent event) {
    _presenceStatus = event.statusName;
    var status = presenceStatuses.where((element) => element.id == event.statusId).firstOrNull;
    if (status != null && status.statusOption == StatusOption.offline) {
      _loggedIn = false;
      _userName = null;
    }
  }

  void _workAssigned(WorkAssignedEvent event) {
    _workAssignments.add(WorkAssignment(event.workId, event.workTargetId, event.channelName));
  }

  void _workAccepted(WorkAcceptedEvent event) {
    _acceptedWorkIds.add(event.workId);
  }

  void _chatEstablished(ChatEstablishedEvent event) {
    _chatMessages.addAll(event.messages);
  }

  void _chatRequest(ChatRequestEvent event) {
    _chatMessages.addAll(event.messages);
  }

  void _conversationMessage(ConversationMessageEvent event) {
    _conversationMessages.add(event);
  }

  bool get isLoggedIn => _loggedIn;

  PresenceStatus getPresenceStatus(StatusOption option) {
    return presenceStatuses.where((element) => element.statusOption == option).firstOrNull!;
  }

  SessionState assertToken() {
    if (token.isEmpty) {
      fatalError("No current session token");
    }
    return this;
  }

  WorkAssignment getWorkAssignment(int assignmentNumber) {
    int index = --assignmentNumber;
    if (index < 0 || index >= _workAssignments.length) {
      fatalError("Invalid work assignment number: $assignmentNumber");
    }
    return _workAssignments[index];
  }

  SessionState removeWorkAssignment(WorkAssignment wa) {
    var clone = _cloneMe();
    if (!clone._workAssignments.remove(wa)) {
      return this;
    }
    clone._acceptedWorkIds.remove(wa.workId);

    clone.save();
    return clone;
  }

  void save() {
    if (!homeDir.existsSync()) {
      homeDir.createSync(recursive: true);
    }
    _file.writeAsStringSync(toString());
  }

  factory SessionState.fromMap(Map<String, dynamic> map) {
    var state = SessionState(map['orgId'], map['token'], PresenceStatus.listFromNode(map['presenceStatuses']));
    state._loggedIn = map['loggedIn'] ?? false;
    state._userName = map['userName'];
    state._presenceStatus = map['presenceStatus'];
    state._workAssignments =
        List<WorkAssignment>.from(map['workAssignments'].map((assignment) => WorkAssignment.fromMap(assignment)));
    state._acceptedWorkIds = List.castFrom(map['acceptedWorkIds']);
    state._chatMessages = List<ChatMessage>.from(map['chatMessages'].map((message) => ChatMessage(message)));
    state._conversationMessages =
        List<ConversationMessageEvent>.from(map['conversationMessages'].map((message) => ConversationMessageEvent(message)));
    return state;
  }

  SessionState setSessionResponse(StartSessionResponse resp) {
    if (token == resp.sessionToken) {
      return this;
    }
    var state = _clone(resp.sessionToken, resp.presenceStatuses);
    state.save();
    return state;
  }

  SessionState clearSession() {
    var newState = _clone();
    newState.save();
    return newState;
  }

  SessionState _cloneMe() {
    return _clone(token, presenceStatuses);
  }

  SessionState _clone([String token = "", List<PresenceStatus> presenceStatuses = const []]) {
    var state = SessionState(orgId, token, presenceStatuses);
    state._file = _file;
    if (token.isNotEmpty) {
      state._loggedIn = _loggedIn;
      state._userName = _userName;
      state._chatMessages = List.of(_chatMessages);
      state._conversationMessages = List.of(_conversationMessages);
      state._workAssignments = List.of(_workAssignments);
      state._acceptedWorkIds = List.of(_acceptedWorkIds);
    }
    return state;
  }

  void _buildPresenceStatuses(StringIndentWriter sw) {
    sw.addLine("Presence statuses:");
    sw.indent();
    for (var status in presenceStatuses) {
      sw.addLine("$status");
    }
    sw.unIndent();
  }

  void _buildWorkAssignments(StringIndentWriter sw) {
    if (_workAssignments.isEmpty) {
      return;
    }
    sw.addLine("Work assignments:");
    sw.indent();
    var counter = 1;
    for (var assignment in _workAssignments) {
      sw.addLine("$counter - $assignment");
      counter++;
    }
    sw.unIndent();
  }

  void _buildAcceptedWorkIds(StringIndentWriter sw) {
    if (_acceptedWorkIds.isEmpty) {
      return;
    }
    sw.addLine("Accepted work ids:");
    sw.indent();
    for (var workId in _acceptedWorkIds) {
      sw.addLine(workId);
    }
    sw.unIndent();
  }

  void _buildChatMessages(StringIndentWriter sw) {
    if (_chatMessages.isEmpty) {
      return;
    }
    sw.addLine("Chat messages:");
    sw.indent();
    for (var message in _chatMessages) {
      sw.addLine("$message");
    }
    sw.unIndent();
  }

  void _buildConversationMessages(StringIndentWriter sw) {
    if (_conversationMessages.isEmpty) {
      return;
    }
    sw.addLine("Conversation messages:");
    sw.indent();
    for (var message in _conversationMessages) {
      sw.addLine("$message");
    }
    sw.unIndent();
  }

  String describe() {
    var sw = StringIndentWriter('  ');
    sw.addLine("orgId: $orgId");
    if (token.isEmpty) {
      sw.addLine("No current session.");
    } else {
      sw.addLine("Token: $token");
      _buildPresenceStatuses(sw);

      if (_loggedIn) {
        sw.addLine("Logged in username is $_userName");
      }

      _buildWorkAssignments(sw);
      _buildAcceptedWorkIds(sw);
      _buildChatMessages(sw);
      _buildConversationMessages(sw);
    }
    return sw.toString();
  }

  SessionState processMessage(String body) {
    var pushEvent = parsePushNotificationEvent(body);
    var event = pushEvent.pollingEvent;
    if (event == null) {
      print("> Received message ${pushEvent.messageType}");
    } else {
      print("> Received $event");
      var handler = mapper[event.eventType];
      if (handler != null) {
        var newState = _clone(token, presenceStatuses);
        handler(newState, event);
        newState.save();
        return newState;
      }
    }
    return this;
  }

  bool hasSession() => token.isNotEmpty;
}

final homeDir = Directory(formHomePath(".1440/shim-test/sessions"));

SessionState loadFromProcessor(CommandLineProcessor processor) {
  return loadSessionState(getProfile(processor));
}

SessionState loadSessionState(Profile profile) {
  File file = File("${homeDir.path}${Platform.pathSeparator}${profile.name}.json");
  SessionState state;
  if (!file.existsSync()) {
    state = SessionState(profile.orgId, "", []);
  } else {
    var map = jsonDecode(file.readAsStringSync());
    state = SessionState.fromMap(map);
    assert(state.orgId == profile.orgId, "Org id does not match session state.");
  }
  state._file = file;
  return state;
}
