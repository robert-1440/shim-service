import 'dart:io';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/conversation_client.dart';
import 'package:cli/src/client/manager.dart';
import 'package:cli/src/client/presence_client.dart';
import 'package:cli/src/client/session_client.dart';
import 'package:cli/src/client/support/presence.dart';
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

  SessionState state;

  bool _started = false;

  bool _loggingIn = false;

  bool _loggedIn = false;

  SmokeTester(ClientManager clientManager, this.state, this._poller)
      : sessionClient = clientManager.getSessionClient(),
        presenceClient = clientManager.getPresenceClient(),
        conversationClient = clientManager.getConversationClient() {
    _poller.stateStream.listen((event) => _stateChanged(event));
    _poller.eventStream.listen((event) => _notificationEvent(event));
  }

  void start() {
    if (!_started) {
      _setupKeyHandler();
      _started = true;
    }
    _poller.start();
  }

  void _sendMessage(String workTargetId, String message) {
    conversationClient.sendMessage(state.token, workTargetId, message).onError(fatalErrorFromAsync);
  }

  void _handleChatRequest(ChatRequestEvent event) {
    for (var message in event.messages) {
      if (message.content.toLowerCase() == "accept work") {
        for (var assignment in state.workAssignments) {
          presenceClient
              .acceptWork(state.token, assignment.workId, assignment.workTargetId)
              .then((_) => _sendMessage(assignment.workTargetId, "Hello, I'm here to help you."));
        }
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
    this.state = state;
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
