import "dart:convert";
import "dart:io";

import 'package:crypto/crypto.dart';
import "_init.dart";
import "http.dart";
import "ini_parser.dart";

var verbose = false;

abstract class AbstractCredentials {
  String _sign(String path, String method, int requestTime, String? body);

  void _finishAuth(RequestBuilder b, String signature, int requestTime);

  void auth(RequestBuilder b) {
    Uri uri = Uri.parse(b.url);
    var requestTime = currentTimeMillis();
    var sig = _sign(uri.path, b.method.name, requestTime, b.getBody());
    _finishAuth(b, sig, requestTime);
  }
}

class Credentials extends AbstractCredentials {
  final String name;

  final String clientId;

  final List<int> _secretBytes;

  late Hmac _mac;

  Credentials(this.name, this.clientId, String password) : _secretBytes = utf8.encode(password) {
    _mac = Hmac(sha256, _secretBytes);
  }

  @override
  void _finishAuth(RequestBuilder b, String signature, int requestTime) {
    var signingString = "$name:$requestTime:$signature";
    var token = base64Encode(utf8.encode(signingString));
    b.authorization("1440-HMAC-SHA256-A", token);
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
    var digest = _mac.convert(utf8.encode(sig));
    return digest.toString();
  }
}

class Profile {
  final String _url;

  final Credentials _credentials;

  final String env;

  Profile.$(String url, this._credentials, this.env) : _url = joinPaths(url, "shim-service/");

  RequestBuilder newRequestBuilder(String uri, Method method) {
    return RequestBuilder(joinPaths(_url, uri), method);
  }

  void configAuth(RequestBuilder b) {
    _credentials.auth(b);
  }
}

void _fatal(String message) {
  stderr.writeln(message);
  exit(2);
}

Profile loadProfile(String profileName) {
  var ini = _loadIni("profiles");
  var section = ini.getRequired(profileName, thing: "profile");
  var url = section['shim.url'] ?? "https://shim-prod.1440.io";
  var clientId = section.getRequired("shim.clientid");
  var name = section.getRequired("shim.name");
  var password = section.getRequired("shim.password");
  var env = section.getRequired("shim.env");

  return Profile.$(url, Credentials(name, clientId, password), env);
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

String formHomePath(String path) {
  return "${getHomePath()}/$path";
}
