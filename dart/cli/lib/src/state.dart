import 'dart:convert';
import 'dart:io';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/presence.dart';
import 'package:cli/src/client/support/session.dart';

class SessionState extends Mappable {
  final String token;

  final List<PresenceStatus> presenceStatuses;

  late File _file;

  SessionState(this.token, this.presenceStatuses);

  @override
  Map<String, dynamic> toMap() {
    return {
      'token': token,
      'presenceStatuses': presenceStatuses.map((status) => status.toMap()).toList(),
    };
  }

  void assertToken() {
    if (token.isEmpty) {
      fatalError("No current session token");
    }
  }

  void save() {
    if (!homeDir.existsSync()) {
      homeDir.createSync(recursive: true);
    }
    _file.writeAsStringSync(jsonEncode(toMap()));
  }

  factory SessionState.fromMap(Map<String, dynamic> map) {
    return SessionState(map['token'], map['presenceStatuses'].map((m) => PresenceStatus.fromMap(m)).toList());
  }

  SessionState setSessionResponse(StartSessionResponse resp) {
    if (token == resp.sessionToken) {
      return this;
    }
    var state = SessionState(resp.sessionToken, resp.presenceStatuses);
    state._file = _file;
    state.save();
    return state;
  }
}

final homeDir = Directory(formHomePath(".1440/shim-test/sessions"));

SessionState loadSessionState(Profile profile) {
  File file = File("${homeDir.path}${Platform.pathSeparator}${profile.name}.json");
  SessionState state;
  if (!file.existsSync()) {
    state = SessionState("", []);
  } else {
    var map = jsonDecode(file.readAsStringSync());
    state = SessionState.fromMap(map);
  }
  state._file = file;
  return state;
}
