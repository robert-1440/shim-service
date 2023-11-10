import 'dart:convert';

import 'package:cli/src/cli/util.dart';
import 'package:cli/src/client/http.dart';
import 'package:cli/src/client/profile.dart';

String? _toStringBody(dynamic value) {
  if (value != null) {
    if (value is! String) {
      if (value is Map) {
        value = jsonEncode(value);
      } else if (value is Mappable) {
        value = jsonEncode(value.toMap());
      } else {
        value = value.toString();
      }
    }
  }
  return value;
}

abstract class BaseClient {
  final Profile _profile;

  BaseClient(this._profile);

  String baseUri();

  void handleAuth(RequestBuilder b);

  RequestBuilder newGetBuilder(String uri) => newRequestBuilder(uri, Method.GET);

  RequestBuilder newPostBuilder(String uri) => newRequestBuilder(uri, Method.POST);

  RequestBuilder newPutBuilder(String uri) => newRequestBuilder(uri, Method.PUT);

  RequestBuilder newRequestBuilder(String uri, Method method) {
    return _profile.newRequestBuilder(joinPaths(baseUri(), uri), method);
  }

  RequestBuilder newDeleteBuilder(String uri) {
    return _profile.newRequestBuilder(joinPaths(baseUri(), uri), Method.DELETE);
  }

  Future<Map<String, dynamic>> getRequiredJson(String uri) async {
    var result = await getJson(uri);
    if (result == null) {
      throw StateError("No body");
    }
    return result;
  }

  Future<Map<String, dynamic>?> getJson(String uri, {bool nullIfNotFound = false}) async {
    try {
      var resp = await get(uri, nullIfNotFound);
      var body = resp.body ?? "";
      if (body.isEmpty) {
        return null;
      }
      return jsonDecode(body);
    } on HttpResourceNotFoundException {
      if (nullIfNotFound) {
        return null;
      }
      rethrow;
    }
  }

  Future<Map<String, dynamic>?> postJson(String url, dynamic inBody) async {
    return await _exchangeJson(Method.POST, url, inBody: inBody);
  }

  Future<Map<String, dynamic>?> putJson(String url, dynamic inBody) async {
    return await _exchangeJson(Method.PUT, url, inBody: inBody);
  }

  Future<Map<String, dynamic>?> patchJson(String url, dynamic inBody) async {
    return await _exchangeJson(Method.PATCH, url, inBody: inBody);
  }

  Future<Map<String, dynamic>?> _exchangeJson(Method method, String uri, {dynamic inBody}) async {
    var resp = await _exchangeBody(method, uri, MediaType.JSON, contentType: MediaType.JSON, body: _toStringBody(inBody));
    var body = resp.body ?? "";
    return body.isEmpty ? null : jsonDecode(body);
  }

  Future<HttpResponse> get(String uri, [bool notFoundOk = false]) async {
    var b = newGetBuilder(uri);
    handleAuth(b);
    return send(b, notFoundOk);
  }

  Future<HttpResponse> delete(String uri) async {
    var b = newRequestBuilder(uri, Method.DELETE);
    handleAuth(b);
    return send(b);
  }

  Future<HttpResponse> _exchangeBody(Method method, String uri, MediaType acceptType,
      {MediaType? contentType, String? body}) async {
    var b = newRequestBuilder(uri, method).accept(acceptType);
    if (contentType != null) {
      assert(body != null && body.isNotEmpty);
      b.contentType(contentType).body(body!);
    } else {
      assert(body == null || body.isEmpty);
    }
    handleAuth(b);
    return send(b);
  }

  Future<HttpResponse> send(RequestBuilder b, [bool notFoundOk = false]) async {
    try {
      return await b.send();
    } on HttpClientException catch (ex) {
      if (!notFoundOk || ex.statusCode != 404) {
        try {
          Map<String, dynamic> record = jsonDecode(ex.body);
          var errorMessage = record['errorMessage'];
          if (errorMessage != null) {
            fatalError(errorMessage);
          }
        } catch (e) {
          // OK
        }
      }
      rethrow;
    }
  }

  Future<HttpResponse> post(String uri, MediaType acceptType, {MediaType? contentType, String? body}) async {
    return _exchangeBody(Method.POST, uri, acceptType, contentType: contentType, body: body);
  }

  Future<HttpResponse> patch(String uri, MediaType acceptType, {MediaType? contentType, String? body}) async {
    return _exchangeBody(Method.PATCH, uri, acceptType, contentType: contentType, body: body);
  }

  Future<HttpResponse> put(String uri, MediaType acceptType, {MediaType? contentType, String? body}) async {
    return _exchangeBody(Method.PUT, uri, acceptType, contentType: contentType, body: body);
  }

}

abstract class CredsBasedClient extends BaseClient {
  CredsBasedClient(super.profile);

  @override
  void handleAuth(RequestBuilder b) {
    _profile.configAuth(b);
  }
}
