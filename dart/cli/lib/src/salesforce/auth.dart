import 'dart:convert';
import 'dart:io';
import 'package:cli/src/xml_util.dart';
import 'package:xml/xml.dart';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/profile.dart';

class AuthInfo extends Mappable {
  String serverUrl;
  String sessionId;
  String userId;
  String orgId;
  int expireTime;

  AuthInfo(this.sessionId, this.serverUrl, this.userId, this.orgId, this.expireTime);

  @override
  Map<String, dynamic> toMap() {
    return {
      'serverUrl': serverUrl,
      'sessionId': sessionId,
      'userId': userId,
      'orgId': orgId,
      'expireTime': expireTime,
    };
  }

  static AuthInfo fromMap(Map<String, dynamic> map) {
    return AuthInfo(map['sessionId'], map['serverUrl'], map['userId'], map['orgId'], map['expireTime']);
  }
}

class AuthSettings {}

final String cacheFile = formHomePath(".sfdc/generic-auth-cache.json");

AuthInfo _parseAuthInfo(String xml) {
  var doc = XmlDocument.parse(xml);
  var child = getChild(doc.rootElement, "Body/loginResponse/result");
  var userId = getChildString(child, "userId");
  var sessionId = getChildString(child, "sessionId");
  var serverUrl = getChildString(child, "serverUrl");
  var userInfo = getChild(child, "userInfo");
  var orgId = getChildString(userInfo, "organizationId");
  var secondsValid = int.parse(getChildString(userInfo, "sessionSecondsValid"));
  if (orgId.length > 15) {
    orgId = orgId.substring(0, 15);
  }
  var expireTime = currentTimeMillis() + (secondsValid * 1000);
  return AuthInfo(sessionId, serverUrl, userId, orgId, expireTime);
}

Future<AuthInfo> _doAuth(String profileName) async {
  final String settingsFile = formHomePath(".sfdc/auth-settings-$profileName.json");
  var f = File(settingsFile);
  if (!f.existsSync()) {
    fatalError("$settingsFile does not exist.");
  }
  var mapped = jsonDecode(f.readAsStringSync());
  String url = mapped['url'];
  String userName = mapped['user'];
  String password = mapped['password'];
  String? token = mapped['token'];
  if (token != null) {
    password += token;
  }
  var headers = {'content-type': 'text/xml', 'SOAPAction': "login"};
  var xml = """<soapenv:Envelope xmlns:soapenv='http://schemas.xmlsoap.org/soap/envelope/' xmlns:xsi='http://www.w3.org/2001/XMLSchema-instance' xmlns:urn='urn:partner.soap.sforce.com'>
    <soapenv:Body>
      <urn:login>
        <urn:username><![CDATA[$userName]]></urn:username>
        <urn:password><![CDATA[$password]]></urn:password>
      </urn:login>
    </soapenv:Body>
  </soapenv:Envelope>
  """;
  var client = getHttpClient();
  var resp = await client.post(url, MediaType.ALL, headers: headers, body: xml);
  return _parseAuthInfo(resp.body!);
}

Future<AuthInfo> _getFromCache(String envName) async {
  var f = File(cacheFile);
  Map<String, dynamic> mapped;
  if (f.existsSync()) {
    var data = f.readAsStringSync();
    mapped = jsonDecode(data);
    var node = mapped[envName];
    if (node != null) {
      var info = AuthInfo.fromMap(node);
      var now = currentTimeMillis();
      if (now < info.expireTime) {
        return info;
      }
    }
  } else {
    mapped = <String, dynamic>{};
  }
  var info = await _doAuth(envName);
  mapped[envName] = info.toMap();
  var encoded = jsonEncode(mapped);
  f.writeAsStringSync(encoded);
  return info;
}

Future<AuthInfo> getAuthInfo(String envName) async {
  return await _getFromCache(envName);
}
