import 'dart:io';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/conversation_client.dart';
import 'package:cli/src/client/manager.dart';
import 'package:cli/src/client/presence_client.dart';
import 'package:cli/src/client/session_client.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/client/support/session.dart';
import 'package:cli/src/modules/main.dart';
import 'package:cli/src/notification/base.dart';
import 'package:cli/src/notification/events/agent.dart';
import 'package:cli/src/poll.dart';
import 'package:cli/src/state.dart';

final acceptRegex = RegExp(r"Accept #(\d+)");

class SmokeTester {
  final SessionClient sessionClient;

  final PresenceClient presenceClient;

  final ConversationClient conversationClient;

  final Poller _poller;

  final StartSessionRequest startSessionRequest;

  SessionState state;

  bool _started = false;

  bool _loggingIn = false;

  bool _startingSession = false;

  bool _sessionStarted = false;

  bool _loggedIn = false;

  SmokeTester(ClientManager clientManager, this.state, this._poller, this.startSessionRequest)
      : sessionClient = clientManager.getSessionClient(),
        presenceClient = clientManager.getPresenceClient(),
        conversationClient = clientManager.getConversationClient() {
    _poller.stateStream.listen((event) => _stateChanged(event));
    _poller.eventStream.listen((event) => _notificationEvent(event));
  }

  void _startSession() {
    if (_startingSession) {
      return;
    }
    _startingSession = true;
    print("Attempting to start session ...");
    startSession(state, sessionClient, startSessionRequest).then(_stateChanged).onError(fatalErrorFromAsync);
  }

  void _handleChatRequest(ChatRequestEvent event) {
    for (var message in event.messages) {
      var match = acceptRegex.firstMatch(message.content);
      if (match != null) {
        var workNumber = int.parse(match.group(1)!);
        var assignment = state.findWorkAssignment(workNumber);
        if (assignment == null) {
          print("Work $workNumber not found.");
          continue;
        }
        print("Accepting work $workNumber ...");
        presenceClient.acceptWork(state.token, assignment.workId, assignment.workTargetId).onError(fatalErrorFromAsync);
      }
    }
  }

  void _notificationEvent(PushNotificationEvent notificationEvent) {
    var event = notificationEvent.pollingEvent;
    if (event == null) {
      return;
    }
    if (event is ChatRequestEvent) {
      _handleChatRequest(event);
      return;
    }
    if (event is LoginResultEvent) {
      _loggingIn = false;
      return;
    }
  }

  Future<void> _login() async {
    if (_loggingIn) {
      return;
    }
    _loggingIn = true;
    print("Attempting to log in ...");
    presenceClient.setPresenceStatus(state.token, state.getPresenceStatus(StatusOption.online).id).onError(fatalErrorFromAsync);
  }

  void _stateChanged(SessionState state) async {
    print("Saw state change, state counter is ${state.stateCounter}.");
    if (!_started) {
      _started = true;
      _setupKeyHandler();
    }

    this.state = state;
    if (!_sessionStarted) {
      if (!state.hasSession()) {
        _startSession();
        return;
      }
      _sessionStarted = true;
      _startingSession = false;
    }

    if (!_loggedIn) {
      if (!state.isLoggedIn) {
        _login();
        return;
      }
      _loggedIn = true;
    }
  }

  void _setupKeyHandler() {
    stdin.echoMode = false;
    stdin.lineMode = false;
    stdin.echoNewlineMode = false;
    print("Starting, press ESC to exit ...");

    stdin.listen((List<int> data) {
      if (data.length == 1 && data.first == 27) {
        print("ESC key pressed. Exiting...");
        stdin.echoMode = true;
        stdin.lineMode = true;
        stdin.echoNewlineMode = true;
        exit(0);
      }
    });
  }
}
