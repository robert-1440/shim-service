import 'dart:convert';

import 'package:cli/src/client/base.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/session.dart';
import '../salesforce/auth.dart' as auth;

class SessionClient extends CredsBasedClient {
  final Profile _profile;

  SessionClient(super.profile) : _profile = profile;

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
      return StartSessionResponse.fromMap(resp.statusCode == 201, jsonDecode(resp.body!));
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
    await delete("$orgId/sessions/$token");
  }

  Future<auth.AuthInfo> getAuthInfo() async {
    return await auth.getAuthInfo(_profile.env);
  }
}
