import 'dart:convert';

import 'package:cli/src/client/base.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/exceptions.dart';
import 'package:cli/src/client/support/session.dart';
import '../salesforce/auth.dart' as auth;
import '../salesforce/auth.dart' as auth;

class PresenceClient extends CredsBasedClient {
  PresenceClient(super.profile);

  @override
  String baseUri() {
    return "presence/actions";
  }

  Future<void> setPresenceStatus(String token, String statusId) async {
    await postWithToken("set-status", token, MediaType.ALL, contentType: MediaType.JSON, body: jsonEncode({"id": statusId}));
  }

  Future<HttpResponse> postWithToken(String uri, String token, MediaType acceptType, {MediaType? contentType, String? body}) async {
    var headers = {'X-1440-Session-Token': token};
    return post(uri, acceptType, contentType: contentType, body: body, headers: headers);
  }
}
