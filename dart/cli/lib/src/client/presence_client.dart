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

  Future<void> acceptWork(String token, String workId, String workTargetId) async {
    await postWithToken("accept-work", token, MediaType.ALL,
        contentType: MediaType.JSON, body: jsonEncode({"workId": workId, "workTargetId": workTargetId}));
  }

  Future<void> closeWork(String token, String workTargetId) async {
    await postWithToken("close-work", token, MediaType.ALL,
        contentType: MediaType.JSON, body: jsonEncode({"workTargetId": workTargetId}));
  }
}
