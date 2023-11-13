import 'dart:convert';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/base.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/profile.dart';
import 'package:cli/src/client/support/exceptions.dart';
import 'package:cli/src/client/support/session.dart';
import '../salesforce/auth.dart' as auth;
import '../salesforce/auth.dart' as auth;

class ConversationClient extends CredsBasedClient {
  ConversationClient(super.profile);

  @override
  String baseUri() {
    return "work-conversations";
  }

  Future<void> sendMessage(String token, String workTargetId, String messageBody, {String? id}) async {
    id ??= uuid();
    await postWithToken("$workTargetId/messages", token, MediaType.ALL,
        contentType: MediaType.JSON, body: jsonEncode({"id": id, "messageBody": messageBody}));
  }
}
