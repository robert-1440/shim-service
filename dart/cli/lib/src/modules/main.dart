import 'dart:io';

import 'package:cli/src/cli/cli.dart';
import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/channel.dart';
import 'package:cli/src/client/support/exceptions.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/client/support/session.dart';
import 'package:cli/src/poll.dart';
import 'package:cli/src/state.dart';

final _commandLoaders = [
      () => Command("start", "Start a session.", "", _startSession),
      () => Command("end", "End current session.", "", _endSession),
      () => Command("ka", "Keep-alive.", "", _keepSessionAlive),
      () => Command("state", "Show current state.", "", _showState),
      () => Command("login", "Log in.", "", _login),
      () => Command("logout", "Log out.", "", _logout),
      () => Command("accept", "Accept work.", "<work number>", _acceptWork),
      () => Command("busy", "Set status to busy.", "", _busy),
      () => Command("send", "Send a message.", "<work number> <message>", _sendMessage),
      () => Command("close", "Close work.", "<work number>", _closeWork),
];

class MainModule extends Module {
  @override
  List<Command Function()> commandLoaders() {
    return _commandLoaders;
  }

  @override
  String description() {
    return "main";
  }

  @override
  String name() {
    return "main";
  }
}

Future<void> _startSession(CommandLineProcessor processor) async {
  processor.assertNoMore();
  var client = getClientManager(processor).getSessionClient();
  var authInfo = await client.getAuthInfo();
  var deviceToken = "sqs::${getCurrentUser()}";
  var request = StartSessionRequest(
      authInfo.orgId, //
      authInfo.userId,
      authInfo.instanceUrl,
      deviceToken,
      authInfo.sessionId,
      ChannelPlatformType.values //
  );
  var state = loadFromProcessor(processor);
  try {
    var resp = await client.startSession(request);
    state = state.setSessionResponse(resp);
    if (resp.newSession) {
      print("New session started.");
    }
    print("Session expires @ ${resp.expirationTime.toLocal()}");
  } on UserAlreadyLoggedInException catch (ex) {
    print("User already logged in.");
    print("Session token: ${ex.token}");
    exit(1);
  }
}

Future<void> _endSession(CommandLineProcessor processor) async {
  processor.assertNoMore();
  var state = loadFromProcessor(processor).assertToken();

  var client = getClientManager(processor).getSessionClient();
  String phrase;
  try {
    await client.endSession(state.orgId, state.token);
    phrase = "ended";
  } on SessionGoneException {
    phrase = "was gone, and was cleared.";
  }
  state.clearSession();
  print("Session $phrase.");
}

Future<void> _keepSessionAlive(CommandLineProcessor processor) async {
  processor.assertNoMore();
  var state = await _poll(processor);
  var client = getClientManager(processor).getSessionClient();
  var resp = await client.keepSessionAlive(state.orgId, state.token);
  print("Session kept alive, expire time is now ${resp.expirationTime}.");
}

Future<void> _showState(CommandLineProcessor processor) async {
  processor.assertNoMore();
  var state = await _poll(processor);

  print(state.describe());
}

Future<SessionState> _poll(CommandLineProcessor processor, [SessionState? state]) async {
  state ??= loadFromProcessor(processor);
  var newState = await poll(getProfile(processor), state);
  state.assertToken();
  return newState;
}

Future<void> _setPresenceStatus(CommandLineProcessor processor, StatusOption statusOption) async {
  processor.assertNoMore();
  var state = await _poll(processor);
  var client = getClientManager(processor).getPresenceClient();
  await client.setPresenceStatus(state.token, state
      .getPresenceStatus(statusOption)
      .id);
}

Future<void> _login(CommandLineProcessor processor) async {
  await _setPresenceStatus(processor, StatusOption.online);
  print("Logged in.");
}

Future<void> _logout(CommandLineProcessor processor) async {
  await _setPresenceStatus(processor, StatusOption.offline);
  print("Logged out.");
}

Future<void> _busy(CommandLineProcessor processor) async {
  await _setPresenceStatus(processor, StatusOption.busy);
  print("Status set to busy.");
}

Future<void> _acceptWork(CommandLineProcessor processor) async {
  var workNumber = processor.nextInt("work number");
  processor.assertNoMore();

  var state = await _poll(processor);
  var assignment = state.getWorkAssignment(workNumber);

  var client = getClientManager(processor).getPresenceClient();
  await client.acceptWork(state.token, assignment.workId, assignment.workTargetId);

  print("Work '$assignment' accepted.");
}

Future<void> _sendMessage(CommandLineProcessor processor) async {
  var workNumber = processor.nextInt("work number");
  var message = processor.next("message");

  processor.assertNoMore();

  var state = await _poll(processor);
  var assignment = state.getWorkAssignment(workNumber);

  var client = getClientManager(processor).getConversationClient();
  await client.sendMessage(state.token, assignment.workTargetId, message);
  print("Message sent to '${assignment.workTargetId}'.");
}


Future<void> _closeWork(CommandLineProcessor processor) async {
  var workNumber = processor.nextInt("work number");
  processor.assertNoMore();
  var state = await _poll(processor);
  var assignment = state.getWorkAssignment(workNumber);

  var client = getClientManager(processor).getPresenceClient();
  await client.closeWork(state.token, assignment.workTargetId);

  print("Work '$assignment' closed.");

}

