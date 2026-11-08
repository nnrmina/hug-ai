import 'dart:async';
import 'dart:convert';
import 'dart:io';

import 'package:http/http.dart' as http;
import 'package:http/io_client.dart';

import '../auth/device_auth_service.dart';
import '../config/app_config.dart';
import '../errors/app_exception.dart';

class ApiClient {
  static const Duration defaultConnectTimeout = Duration(seconds: 10);
  static const Duration defaultTotalTimeout = Duration(seconds: 20);

  final http.Client _client;
  final String baseUrl;
  final String apiKey;

  /// Upper bound for the whole request (connect + send + response body).
  final Duration timeout;

  /// null → requests are sent without `Authorization` (only /auth/device).
  final AuthTokenProvider? _auth;
  final bool _useSharedAuth;

  ApiClient({
    http.Client? client,
    this.baseUrl = AppConfig.apiBaseUrl,
    this.apiKey = AppConfig.apiKey,
    this.timeout = defaultTotalTimeout,
    AuthTokenProvider? auth,
  })  : _client = client ?? _defaultClient(),
        _auth = auth,
        _useSharedAuth = auth == null;

  /// Client without bearer auth — used for device registration.
  ApiClient.unauthenticated({
    http.Client? client,
    this.baseUrl = AppConfig.apiBaseUrl,
    this.apiKey = AppConfig.apiKey,
    this.timeout = defaultTotalTimeout,
  })  : _client = client ?? _defaultClient(),
        _auth = null,
        _useSharedAuth = false;

  static http.Client _defaultClient() =>
      IOClient(HttpClient()..connectionTimeout = defaultConnectTimeout);

  AuthTokenProvider? get _authProvider =>
      _auth ?? (_useSharedAuth ? DeviceAuthService.shared : null);

  Future<dynamic> getJson(String path, {Map<String, String>? query}) async =>
      _decode(await _execute('GET', path, query: query));

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? query,
  }) async =>
      _asMap(_decode(await _execute('POST', path, query: query, body: body)));

  Future<Map<String, dynamic>> patchJson(
    String path,
    Map<String, dynamic> body, {
    Map<String, String>? query,
  }) async =>
      _asMap(_decode(await _execute('PATCH', path, query: query, body: body)));

  Future<void> delete(String path, {Map<String, String>? query}) async {
    _decode(await _execute('DELETE', path, query: query));
  }

  Uri _uri(String path, Map<String, String>? query) {
    final problem = AppConfig.validateBaseUrl(baseUrl);
    if (problem != null) {
      throw AppException(problem, type: AppErrorType.config);
    }
    final uri = Uri.parse('$baseUrl$path');
    if (query == null || query.isEmpty) return uri;
    return uri.replace(queryParameters: {...uri.queryParameters, ...query});
  }

  Future<http.Response> _execute(
    String method,
    String path, {
    Map<String, String>? query,
    Map<String, dynamic>? body,
  }) async {
    final uri = _uri(path, query);
    final auth = _authProvider;
    if (auth == null) return _send(method, uri, body, null);

    var response = await _send(method, uri, body, await auth.getToken());
    if (response.statusCode != 401) return response;

    // Token missing/expired/invalid: re-register once and retry once.
    response = await _send(method, uri, body, await auth.refreshToken());
    if (response.statusCode == 401) {
      throw AppException(
        'Serverə giriş alınmadı. Zəhmət olmasa tətbiqi bağlayıb yenidən açın.',
        type: AppErrorType.unauthorized,
        statusCode: 401,
        detail: extractDetail(_safeText(response)),
      );
    }
    return response;
  }

  Future<http.Response> _send(
    String method,
    Uri uri,
    Map<String, dynamic>? body,
    String? token,
  ) async {
    final request = http.Request(method, uri);
    request.headers['Accept'] = 'application/json';
    if (apiKey.isNotEmpty) request.headers['X-API-Key'] = apiKey;
    if (token != null) request.headers['Authorization'] = 'Bearer $token';
    if (body != null) {
      request.headers['Content-Type'] = 'application/json; charset=utf-8';
      request.bodyBytes = utf8.encode(jsonEncode(body));
    }
    try {
      return await _client
          .send(request)
          .then(http.Response.fromStream)
          .timeout(timeout);
    } on TimeoutException {
      throw const AppException(
        'Server vaxtında cavab vermədi. Bir az sonra yenidən cəhd edin.',
        type: AppErrorType.timeout,
      );
    } on HandshakeException {
      throw const AppException(
        'Serverlə təhlükəsiz (HTTPS) əlaqə qurulmadı. Telefonun tarix və saatını yoxlayın.',
        type: AppErrorType.tls,
      );
    } on TlsException {
      throw const AppException(
        'Serverlə təhlükəsiz (HTTPS) əlaqə qurulmadı.',
        type: AppErrorType.tls,
      );
    } on SocketException {
      throw const AppException(
        'Serverə qoşulmaq mümkün olmadı. İnternet bağlantısını yoxlayın.',
        type: AppErrorType.network,
      );
    } on http.ClientException {
      throw const AppException(
        'Serverə qoşulmaq mümkün olmadı. İnternet bağlantısını yoxlayın.',
        type: AppErrorType.network,
      );
    } catch (_) {
      throw const AppException(
        'Sorğu göndərilə bilmədi. Yenidən cəhd edin.',
        type: AppErrorType.unknown,
      );
    }
  }

  static String _safeText(http.Response r) =>
      utf8.decode(r.bodyBytes, allowMalformed: true);

  Map<String, dynamic> _asMap(dynamic decoded) =>
      decoded is Map<String, dynamic> ? decoded : <String, dynamic>{};

  dynamic _decode(http.Response response) {
    final code = response.statusCode;
    final text = _safeText(response);
    if (code >= 200 && code < 300) {
      if (text.trim().isEmpty) return null;
      try {
        return jsonDecode(text);
      } on FormatException {
        throw AppException(
          'Serverdən gələn cavab oxuna bilmədi.',
          type: AppErrorType.badResponse,
          statusCode: code,
        );
      }
    }
    throw errorFor(code, extractDetail(text));
  }

  /// Extracts FastAPI-style `detail` (string or validation-error list).
  /// Returns null for non-JSON bodies (e.g. HTML from a proxy).
  static String? extractDetail(String body) {
    try {
      final decoded = jsonDecode(body);
      if (decoded is! Map) return null;
      final detail = decoded['detail'];
      String? out;
      if (detail is String) {
        out = detail;
      } else if (detail is List) {
        final parts = detail
            .map((e) => e is Map ? e['msg']?.toString() : e?.toString())
            .whereType<String>()
            .where((s) => s.isNotEmpty)
            .toList();
        out = parts.isEmpty ? null : parts.join('\n');
      } else if (detail != null) {
        out = detail.toString();
      }
      if (out == null || out.trim().isEmpty) return null;
      out = out.trim();
      return out.length > 300 ? '${out.substring(0, 300)}…' : out;
    } catch (_) {
      return null;
    }
  }

  /// Maps an HTTP error status to a typed exception. 4xx show the backend
  /// `detail` when present; 5xx details stay internal (kept in `detail`).
  static AppException errorFor(int code, String? detail) {
    AppException make(AppErrorType type, String fallback,
            {bool preferDetail = true}) =>
        AppException(
          preferDetail && detail != null ? detail : fallback,
          type: type,
          statusCode: code,
          detail: detail,
        );

    switch (code) {
      case 400:
        return make(AppErrorType.validation, 'Sorğu düzgün deyil.');
      case 401:
        return make(AppErrorType.unauthorized,
            'Serverə giriş alınmadı. Tətbiqi yenidən açın.',
            preferDetail: false);
      case 403:
        return make(AppErrorType.forbidden,
            'Bu əməliyyata icazə yoxdur (API açarını yoxlayın).');
      case 404:
        return make(AppErrorType.notFound, 'Məlumat tapılmadı.');
      case 409:
        return make(AppErrorType.conflict, 'Bu əməliyyat artıq mümkün deyil.');
      case 413:
        return make(AppErrorType.payloadTooLarge,
            'Fayl çox böyükdür (ən çox 10 MB).');
      case 415:
        return make(AppErrorType.unsupportedMedia,
            'Bu fayl formatı dəstəklənmir.');
      case 422:
        return AppException(
          detail != null
              ? 'Məlumat düzgün deyil: $detail'
              : 'Göndərilən məlumat düzgün deyil.',
          type: AppErrorType.validation,
          statusCode: code,
          detail: detail,
        );
      case 429:
        return make(AppErrorType.rateLimited,
            'Çox sayda sorğu göndərildi. Bir az gözləyin.');
    }
    if (code >= 500) {
      return make(AppErrorType.server,
          'Serverdə xəta baş verdi. Bir az sonra yenidən cəhd edin.',
          preferDetail: false);
    }
    return make(AppErrorType.unknown, 'Sorğu uğursuz oldu ($code).');
  }
}
