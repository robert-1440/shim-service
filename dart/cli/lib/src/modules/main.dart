import 'dart:io';

import 'package:cli/src/aws.dart';
import 'package:cli/src/cli/cli.dart';
import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/session_client.dart';
import 'package:cli/src/client/support/channel.dart';
import 'package:cli/src/client/support/exceptions.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/client/support/session.dart';
import 'package:cli/src/poll.dart';
import 'package:cli/src/smoke.dart';
import 'package:cli/src/state.dart';

final _commandLoaders = [
  () => Command("start", "Start a session.", "", _startSession),
  () => Command("end", "End current session.", "", _endSession),
  () => Command("ka", "Keep-alive.", "", _keepSessionAlive),
  () => Command("state", "Show current state.", "", _showState),
  () => Command("login", "Log in.", "", _login),
  () => Command("logout", "Log out.", "", _logout),
  () => Command("accept", "Accept work.", "<work number>", _acceptWork),
  () => Command("decline", "Decline work.", "<work number>", _declineWork),
  () => Command("busy", "Set status to busy.", "", _busy),
  () => Command("send", "Send a message.", "<work number> <message>", _sendMessage),
  () => Command("close", "Close work.", "<work number>", _closeWork),
  () => Command("smoke", "Smoke test.", "", _smokeTest),
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
  var request = await _createStartSessionRequest(client);
  var state = loadFromProcessor(processor);
  await startSession(state, client, request);
}

Future<StartSessionRequest> _createStartSessionRequest(SessionClient client) async {
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
  return request;
}

Future<SessionState> startSession(SessionState state, SessionClient client, StartSessionRequest request) async {
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
  return state;
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
  await client.setPresenceStatus(state.token, state.getPresenceStatus(statusOption).id);
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

Future<void> _declineWork(CommandLineProcessor processor) async {
  var workNumber = processor.nextInt("work number");
  processor.assertNoMore();

  var state = await _poll(processor);
  var assignment = state.getWorkAssignment(workNumber);

  var client = getClientManager(processor).getPresenceClient();
  await client.declineWork(state.token, assignment.workId, assignment.workTargetId);
  state.removeWorkAssignment(assignment);

  print("Work '$assignment' declined.");
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
  state.removeWorkAssignment(assignment);

  print("Work '$assignment' closed.");
}

Future<void> _smokeTest(CommandLineProcessor processor) async {
  processor.assertNoMore();
  var cm = getClientManager(processor);
  var client = cm.getSessionClient();
  var request = await _createStartSessionRequest(client);
  var state = loadFromProcessor(processor);
  state = await startSession(state, client, request);
  var sqs = getSqs(getProfile(processor));
  var user = getCurrentUser();
  var poller = Poller(user, sqs, state);
  var tester = SmokeTester(cm, state, poller);
  tester.start();
}
