import 'package:cli/src/client/base.dart';
import 'package:cli/src/client/presence_client.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/session_client.dart';

class ClientManager {
  final Profile profile;

  final Map<Type, BaseClient> _clientMap = {};

  ClientManager(this.profile);

  dynamic _getClient(Type type, BaseClient Function(Profile profile) creator) {
    var v = _clientMap[type];
    v ??= _clientMap[type] = creator(profile);
    return v;
  }

  SessionClient getSessionClient() {
    return _getClient(SessionClient, (p) => SessionClient(p));
  }

  PresenceClient getPresenceClient() {
    return _getClient(PresenceClient, (p) => PresenceClient(p));
  }
}
