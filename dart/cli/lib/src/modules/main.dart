import 'dart:io';

import 'package:cli/src/cli/cli.dart';
import 'package:cli/src/cli/processor.dart';
import 'package:cli/src/client/_init.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/channel.dart';
import 'package:cli/src/client/support/session.dart';
import 'package:cli/src/state.dart';

final _commandLoaders = [() => Command("start", "Start a session.", "", _startSession)];

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
  var state = loadSessionState(getProfile(processor));
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
