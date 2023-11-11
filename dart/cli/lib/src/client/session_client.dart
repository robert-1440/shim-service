import 'dart:convert';

import 'package:cli/src/client/base.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/support/exceptions.dart';
import 'package:cli/src/client/support/session.dart';

class SessionClient extends CredsBasedClient {
  SessionClient(super.profile);

  @override
  String baseUri() {
    return "organizations";
  }

  /// Starts a session.
  ///
  /// [request] - [StartSessionRequest].
  ///
  /// Throws [UserAlreadyLoggedInException] if a session already exists for the given user.
  ///
  /// Returns [StartSessionResponse]
  ///
  Future<StartSessionResponse> startSession(StartSessionRequest request) async {
    try {
      var resp = await put("${request.orgId}/sessions", MediaType.ALL, contentType: MediaType.JSON, body: request.toJson());
      return StartSessionResponse.fromMap(resp.statusCode == 201, resp.statusCode == 202, jsonDecode(resp.body!));
    } on HttpConflictException catch (ex) {
      throw UserAlreadyLoggedInException(ex.headers['x-1440-session-token']!);
    }
  }

  /// Keeps a session alive.
  ///
  /// [orgId] - Organization ID.
  ///
  /// [token] - Session token.
  ///
  /// Returns [KeepAliveResponse]
  ///
  Future<KeepAliveResponse> keepSessionAlive(String orgId, String token) async {
    var resp = await post("$orgId/sessions/$token/actions/keep-alive", MediaType.ALL);
    return KeepAliveResponse.fromMap(jsonDecode(resp.body!));
  }

  /// Ends a session.
  /// [orgId] - Organization ID.
  /// [token] - Session token.
  ///
  Future<void> endSession(String orgId, String token) async {
    try {
      await delete("$orgId/sessions/$token");
    } on HttpGoneException {
      throw SessionGoneException();
    }
  }

}
