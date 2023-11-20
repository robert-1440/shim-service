import 'dart:io';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/conversation_client.dart';
import 'package:cli/src/client/manager.dart';
import 'package:cli/src/client/presence_client.dart';
import 'package:cli/src/client/session_client.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/notification/base.dart';
import 'package:cli/src/notification/events/agent.dart';
import 'package:cli/src/notification/events/conversational.dart';
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
  }

  void start() {
    if (!_started) {
      _setupKeyHandler();
      _started = true;
    }
    _poller.start();
  }

  Future<void> _sendMessage(String workTargetId, String message) {
    return conversationClient.sendMessage(state.token, workTargetId, message).onError(fatalErrorFromAsync);
  }

  void _handleChatEstablished(ChatEstablishedEvent event) {
    void accepted(WorkAssignment assignment) {
      _sendMessage(assignment.workTargetId, "Hello, I'm here to help you.");
      print("Work Accepted. Send next command (echo, close).");
    }

    for (var message in event.messages) {
      if (message.content.toLowerCase().trim() == "accept work") {
        var assignment = state.workAssignments.where((element) => element.workTargetId == event.workTargetId).firstOrNull;
        if (assignment != null) {
          accepted(assignment);
        }
      }
    }
  }

  void _handleChatRequest(ChatRequestEvent event) {
    for (var message in event.messages) {
      if (message.content.toLowerCase().trim() == "accept work") {
        for (var assignment in state.workAssignments) {
          presenceClient.acceptWork(state.token, assignment.workId, assignment.workTargetId).onError(fatalErrorFromAsync);
        }
      }
    }
  }

  void _handleConversationEvent(ConversationMessageEvent event) {
    var text = event.text.toLowerCase();
    if (text.startsWith("echo ")) {
      var output = event.text.substring(5);
      _sendMessage(event.workId, output);
    } else if (text == "close work") {
      var assignment = state.workAssignments.where((element) => element.workTargetId == event.workId).firstOrNull;
      if (assignment == null) {
        print("Cannot find work for '$event.workId'");
      } else {
        void workClosed() {
          print("Work was closed. Ending session...");
          void endIt() {
            cleanExit(0);
          }

          sessionClient.endSession(state.orgId, state.token).onError(fatalErrorFromAsync).then((_) => _poller.close(endIt));
        }

        void closeIt() {
          print("Closing work ...");
          presenceClient.closeWork(state.token, assignment.workTargetId).onError(fatalErrorFromAsync).then((_) => workClosed());
        }

        _sendMessage(assignment.workTargetId, "Ok! Goodbye then!").then((_) => closeIt());
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
    if (event is ConversationMessageEvent) {
      _handleConversationEvent(event);
      return;
    }
    if (event is ChatEstablishedEvent) {
      _handleChatEstablished(event);
      return;
    }
  }

  Future<void> _login() async {
    if (_loggingIn) {
      return;
    }
    _loggingIn = true;
    print("Logging in ...");
    await presenceClient.setPresenceStatus(state.token, state.getPresenceStatus(StatusOption.online).id);
  }

  void _stateChanged(Pair<SessionState, List<PushNotificationEvent>> eventPair) async {
    state = eventPair.left;
    if (!_loggedIn) {
      if (!state.isLoggedIn) {
        _login();
      } else {
        _loggedIn = true;
        print(">>> Send 'Accept work' message");
      }
    }
    for (var event in eventPair.right) {
      _notificationEvent(event);
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
        cleanExit(0);
      }
    });
  }

  void cleanExit(int code) {
    stdin.echoMode = true;
    stdin.lineMode = true;
    stdin.echoNewlineMode = true;
    exit(0);
  }
}
