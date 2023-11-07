import "dart:convert";
import "dart:io";

import 'package:crypto/crypto.dart';
import "_init.dart";
import "http.dart";
import "ini_parser.dart";

var verbose = false;

abstract class AbstractCredentials {
  String _sign(String path, String method, int requestTime, String? body);

  void _finishAuth(RequestBuilder b);

  void auth(RequestBuilder b) {
    Uri uri = Uri.parse(b.url);
    var requestTime = currentTimeMillis();
    var sig = _sign(uri.path, b.method.name, requestTime, b.getBody());
    b.header("X-1440-Signature", sig);
    b.authorization("1440-HMAC-SHA256", "$requestTime");
    _finishAuth(b);
  }
}

class Credentials extends AbstractCredentials {
  final String name;

  final String clientId;

  final String password;

  final List<int> _secretBytes;

  Hmac? _mac;

  Credentials(this.name, this.clientId, this.password) : _secretBytes = utf8.encode(password);

  @override
  void _finishAuth(RequestBuilder b) {

  }

  @override
  String _sign(String path, String method, int requestTime, String? body) {
    String sig = "$name:$clientId:$path:$method:$requestTime";
    if (body != null && body.isNotEmpty) {
      var h = sha512.convert(utf8.encode(body)).toString();
      sig += ":$h";
    }
    if (verbose) {
      if (body != null && body.isNotEmpty) {
        print(">> Body = $body");
      }
      print("Signing string is: $sig");
    }
    _mac ??= Hmac(sha256, _secretBytes);
    var digest = _mac!.convert(utf8.encode(sig));
    return digest.toString();
  }
}

class UserCredentials extends AbstractCredentials {
  final String userId;

  final String password;

  final List<int> _secretBytes;

  Hmac? _mac;

  UserCredentials(this.userId, this.password) : _secretBytes = utf8.encode(password);

  @override
  void _finishAuth(RequestBuilder b) {
    b.header("X-1440-User-Id", userId);
  }

  @override
  String _sign(String path, String method, int requestTime, String? body) {
    String sig = "$userId:$path:$method:$requestTime";
    if (body != null && body.isNotEmpty) {
      var h = sha512.convert(utf8.encode(body)).toString();
      sig += ":$h";
    }
    if (verbose) {
      if (body != null && body.isNotEmpty) {
        print(">> Body = $body");
      }
      print("Signing string is: $sig");
    }
    _mac ??= Hmac(sha256, _secretBytes);
    var digest = _mac!.convert(utf8.encode(sig));
    return digest.toString();
  }
}

class Profile {
  final String _url;

  final Credentials? _credentials;

  final UserCredentials _userCredentials;

  Profile.$(String url, this._credentials, this._userCredentials) : _url = joinPaths(url, "configuration-service/");

  RequestBuilder newRequestBuilder(String uri, Method method) {
    return RequestBuilder(joinPaths(_url, uri), method);
  }

  void userAuth(RequestBuilder b) {
    _userCredentials.auth(b);
  }

  void configAuth(RequestBuilder b) {
    _credentials!.auth(b);
  }
}

void _fatal(String message) {
  stderr.writeln(message);
  exit(2);
}

UserCredentials _loadUserCredentials(String user) {
  var ini = _loadIni("users");
  var section = ini.getRequired(user);
  return UserCredentials(section.getRequired('userid'), section.getRequired('password'));
}

Credentials _loadConfigCredentials(String configName) {
  var ini = _loadIni("credentials");
  var section = ini.getRequired(configName);
  return Credentials(section.getRequired('name'), section.getRequired('clientid'), section.getRequired('password'));
}

Profile loadProfile(String profileName) {
  var ini = _loadIni("profiles");
  var section = ini.getRequired(profileName, thing: "profile");
  var url = section['url'] ?? "https://configuration.1440.io";
  var creds = section['creds'];
  var configCreds = creds == null ? null : _loadConfigCredentials(creds);
  var user = section['user'];

  UserCredentials grabUserCreds() {
    var userId = section.getRequired("user.id");
    var password = section.getRequired("user.password");
    return UserCredentials(userId, password);
  }

  var userCreds = user == null ? grabUserCreds() : _loadUserCredentials(user);
  return Profile.$(url, configCreds, userCreds);
}

IniFile loadProfiles() {
  return _loadIni("profiles");
}

IniFile _loadIni(String file) {
  File f = getHomeFile(file);
  if (!f.existsSync()) {
    _fatal("$f does not exist.");
  }
  return loadIniFile(f.path);
}

/// Returns the home directory for the current user.
String getHomePath() {
  switch (Platform.operatingSystem) {
    case 'linux':
    case 'macos':
      return Platform.environment['HOME']!;

    case 'windows':
      return Platform.environment['USERPROFILE']!;

    default:
      throw StateError("Unsupported operating system ${Platform.operatingSystem}");
  }
}

/// Returns the current time in milliseconds since epoch.
int currentTimeMillis() {
  return DateTime.now().millisecondsSinceEpoch;
}
