import 'dart:convert';
import 'dart:typed_data';

import '../cli/util.dart';
import 'package:http/http.dart' as http;

var verbose = false;

final contentTypeHeader = "Content-Type";

class HttpResponseException {
  final int statusCode;

  final String body;

  final Map<String, String> headers;

  HttpResponseException(http.Response resp)
      : statusCode = resp.statusCode,
        body = resp.body,
        headers = resp.headers;

  bool is4xx() => statusCode ~/ 100 == 4;

  bool is5xx() => statusCode ~/ 100 == 5;

  String getDetails() {
    var sb = StringBuffer("status: $statusCode");
    if (body.isNotEmpty) {
      sb.writeln("\n\nbody: <<$body>>");
    }
    if (headers.isNotEmpty) {
      sb.writeln("headers:\n${JsonEncoder.withIndent('  ').convert(headers)}");
    }
    return sb.toString();
  }

  @override
  String toString() {
    var sb = StringBuffer();
    sb.write("$statusCode");
    if (body.isNotEmpty) {
      sb.write(": $body");
    }
    return sb.toString();
  }
}

class HttpClientException extends HttpResponseException {
  HttpClientException(http.Response resp) : super(resp);
}

class HttpServerException extends HttpResponseException {
  HttpServerException(http.Response resp) : super(resp);
}

class HttpRedirectException extends HttpResponseException {
  HttpRedirectException(http.Response resp) : super(resp);

  String getLocation() {
    return headers['location']!;
  }
}

class HttpResourceNotFoundException extends HttpClientException {
  HttpResourceNotFoundException(super.resp);
}

enum MediaType {
  X_WWW_FORM_URLENCODED("application/x-www-form-urlencoded"),
  JSON("application/json"),
  XML("text/xml"),
  PLAIN_TEXT("text/plain"),
  ALL("*/*");

  final String _stringValue;

  const MediaType(this._stringValue);

  String getValue() => _stringValue;
}

class HttpResponse {
  final int statusCode;

  final String? body;

  final Uint8List? bodyBytes;

  final Map<String, String> headers;

  HttpResponse(this.statusCode, this.body, this.bodyBytes, this.headers);
}

enum Method {
  POST,
  GET,
  PATCH,
  DELETE,
  PUT;

  bool acceptsBody() {
    return name.startsWith("P");
  }
}

http.Response _checkResponse(http.Response resp) {
  int statusCode = resp.statusCode;
  int base = statusCode ~/ 100;

  if (base != 2) {
    switch (base) {
      case 4:
        if (statusCode == 404) {
          throw HttpResourceNotFoundException(resp);
        }
        throw HttpClientException(resp);

      case 5:
        throw HttpServerException(resp);

      case 3:
        if (statusCode == 302) {
          throw HttpRedirectException(resp);
        }

      default:
        throw HttpResponseException(resp);
    }
  }
  return resp;
}

abstract class IHttpClient {
  Future<HttpResponse> post(String uri, MediaType acceptType, {MediaType? contentType, Map<String, String>? headers, Object? body});

  Future<HttpResponse> get(String uri, MediaType acceptType, {Map<String, String>? headers});

  Future<HttpResponse> patch(String uri, MediaType acceptType,
      {MediaType? contentType, Map<String, String>? headers, Object? body});

  Future<HttpResponse> put(String uri, MediaType acceptType, {MediaType? contentType, Map<String, String>? headers, Object? body});

  Future<HttpResponse> delete(String uri, {MediaType? acceptType, Map<String, String>? headers});

  Future<HttpResponse> exchange(Method method, String uri, MediaType? acceptType,
      {MediaType? contentType, Map<String, String>? headers, Object? body});
}

class _DefaultHttpClient implements IHttpClient {
  final ILowLevelHttpClient client = _DefaultLowLevelClient();

  @override
  Future<HttpResponse> post(String uri, MediaType acceptType,
          {MediaType? contentType, Map<String, String>? headers, Object? body}) =>
      exchange(Method.POST, uri, acceptType, contentType: contentType, headers: headers, body: body);

  @override
  Future<HttpResponse> delete(String uri, {MediaType? acceptType, Map<String, String>? headers}) =>
      exchange(Method.DELETE, uri, acceptType, headers: headers);

  @override
  Future<HttpResponse> get(String uri, MediaType acceptType, {Map<String, String>? headers}) =>
      exchange(Method.GET, uri, acceptType, headers: headers);

  @override
  Future<HttpResponse> patch(String uri, MediaType acceptType,
          {MediaType? contentType, Map<String, String>? headers, Object? body}) =>
      exchange(Method.PATCH, uri, acceptType, contentType: contentType, headers: headers, body: body);

  @override
  Future<HttpResponse> put(String uri, MediaType acceptType,
          {MediaType? contentType, Map<String, String>? headers, Object? body}) =>
      exchange(Method.PATCH, uri, acceptType, contentType: contentType, headers: headers, body: body);

  Map<String, String> _createHeaders(MediaType? contentType, MediaType? acceptType, Map<String, String>? headers) {
    var requestHeaders = <String, String>{};
    if (headers != null) {
      requestHeaders.addAll(headers);
    }
    if (contentType != null) {
      requestHeaders.putIfAbsent("Content-Type", () => contentType.getValue());
    }
    if (acceptType != null) {
      requestHeaders.putIfAbsent("Accept", () => acceptType.getValue());
    }
    return requestHeaders;
  }

  @override
  Future<HttpResponse> exchange(Method method, String uri, MediaType? acceptType,
      {MediaType? contentType, Map<String, String>? headers, Object? body}) async {
    acceptType ??= MediaType.ALL;
    if (body != null && body is! String) {
      body = jsonEncode(body);
    }
    var url = Uri.parse(uri);
    var requestHeaders = _createHeaders(contentType, acceptType, headers);

    Future<http.Response> inner(Uri url) async {
      switch (method) {
        case Method.POST:
          return client.post(url, headers: requestHeaders, body: body);

        case Method.GET:
          return client.get(url, headers: requestHeaders);

        case Method.PATCH:
          return client.patch(url, headers: requestHeaders, body: body);

        case Method.DELETE:
          return client.delete(url, headers: requestHeaders);

        case Method.PUT:
          return client.put(url, headers: requestHeaders, body: body);
      }
    }

    for (;;) {
      try {
        var resp = _checkResponse(await inner(url));
        return HttpResponse(resp.statusCode, resp.body, resp.bodyBytes, resp.headers);
      } on HttpRedirectException catch (ex, _) {
        url = Uri.parse(ex.getLocation());
        continue;
      }
    }
  }
}

abstract class ILowLevelHttpClient {
  Future<http.Response> get(Uri url, {Map<String, String>? headers});

  Future<http.Response> post(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding});

  Future<http.Response> put(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding});

  Future<http.Response> patch(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding});

  Future<http.Response> delete(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding});
}

class _DefaultLowLevelClient implements ILowLevelHttpClient {
  @override
  Future<http.Response> delete(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding}) {
    return http.delete(url, headers: headers, body: body, encoding: encoding);
  }

  @override
  Future<http.Response> get(Uri url, {Map<String, String>? headers}) {
    return http.get(url, headers: headers);
  }

  @override
  Future<http.Response> patch(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding}) {
    return http.patch(url, headers: headers, body: body, encoding: encoding);
  }

  @override
  Future<http.Response> post(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding}) {
    return http.post(url, headers: headers, body: body, encoding: encoding);
  }

  @override
  Future<http.Response> put(Uri url, {Map<String, String>? headers, Object? body, Encoding? encoding}) {
    return http.put(url, headers: headers, body: body, encoding: encoding);
  }
}

IHttpClient? client;

IHttpClient getHttpClient() {
  client ??= _DefaultHttpClient();
  return client!;
}

class RequestBuilder {
  final String url;

  final Method method;

  final Map<String, String> _headers = {};

  String? _body;

  MediaType _acceptType = MediaType.ALL;

  RequestBuilder(this.url, this.method);

  RequestBuilder body(String body) {
    if (!method.acceptsBody()) {
      throw StateError("Body not allowed for ${method.name}.");
    }
    _body = body;
    return this;
  }

  String? getBody() => _body;

  RequestBuilder header(String name, String value) {
    _headers[name] = value;
    return this;
  }

  RequestBuilder accept(MediaType mediaType) {
    _acceptType = mediaType;
    return this;
  }

  RequestBuilder authorization(String tokenTypeOrToken, [String? token]) {
    if (token != null) {
      token = "$tokenTypeOrToken $token";
    } else {
      token = tokenTypeOrToken;
    }
    return header("Authorization", token);
  }

  RequestBuilder contentType(MediaType mediaType) {
    return header("Content-Type", mediaType._stringValue);
  }

  Future<HttpResponse> send() async {
    if (verbose) {
      print("Builder content:\n${describe()}");
    }
    return await getHttpClient().exchange(method, url, _acceptType, headers: _headers, body: _body);
  }

  String describe() {
    var lb = LayoutBuilder();
    lb.add("Action", "${method.name} $url");
    if (_headers.isNotEmpty) {
      lb.add("Headers", LayoutBuilder.formatMap(_headers));
    }
    if (_body != null && _body!.isNotEmpty) {
      lb.add("Body", _body);
    }
    return lb.toString();
  }
}

String joinPaths(String base, String uri) {
  String full = base;
  if (!full.endsWith("/") && !uri.startsWith("/")) {
    full += "/";
  }
  return full + uri;
}

String encodeForUrl(String data) {
  return Uri.encodeComponent(data);
}
