import 'dart:convert';
import 'dart:io';

import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:yaxin_ai_mobile/core/auth/device_auth_service.dart';
import 'package:yaxin_ai_mobile/core/config/app_config.dart';
import 'package:yaxin_ai_mobile/core/errors/app_exception.dart';
import 'package:yaxin_ai_mobile/core/network/api_client.dart';

const _base = 'http://test/api/v1';

http.Response _utf8(String body, int code) => http.Response.bytes(
    utf8.encode(body), code,
    headers: {'content-type': 'application/json; charset=utf-8'});
const _legacy = '3f2504e0-4f89-41d3-9a0c-0305e82c3301';

/// Fake backend emulating backend/app/api/v1/auth.py: device accounts with
/// secrets, a once-only legacy claim, and bearer-protected endpoints.
class _Backend {
  int registrations = 0;
  final List<Map<String, dynamic>> registrationBodies = [];
  final List<String?> authHeaders = [];
  final Set<String> valid = {};
  final Map<String, String> accounts = {}; // user_id -> device_secret
  final Set<String> claimedLegacy = {};
  String? apiKeySeen;

  late final MockClient client = MockClient((req) async {
    apiKeySeen = req.headers['X-API-Key'];
    if (req.url.path.endsWith('/auth/device')) {
      expect(req.headers.containsKey('Authorization'), isFalse);
      registrations++;
      final body = jsonDecode(req.body) as Map<String, dynamic>;
      registrationBodies.add(body);
      final token = 'tok$registrations';
      String userId;
      String? secret;
      if (body['user_id'] != null || body['device_secret'] != null) {
        if (accounts[body['user_id']] != body['device_secret']) {
          return _utf8(
              jsonEncode({'detail': 'Cihaz məlumatları yanlışdır.'}), 401);
        }
        userId = body['user_id'] as String;
      } else {
        final legacy = body['legacy_user_id'] as String?;
        if (legacy != null && claimedLegacy.add(legacy)) {
          userId = legacy;
        } else {
          userId = 'u-${accounts.length + 1}';
        }
        secret = 'sec-$userId';
        accounts[userId] = secret;
      }
      valid.add(token);
      return http.Response(
          jsonEncode({
            'access_token': token,
            'token_type': 'bearer',
            'user_id': userId,
            'expires_at': DateTime.now()
                .toUtc()
                .add(const Duration(hours: 1))
                .toIso8601String(),
            'device_secret': secret,
          }),
          200);
    }
    final header = req.headers['Authorization'];
    authHeaders.add(header);
    final token = header?.replaceFirst('Bearer ', '');
    if (token == null || !valid.contains(token)) {
      return _utf8(jsonEncode({'detail': 'Token etibarsızdır'}), 401);
    }
    return http.Response(jsonEncode({'ok': true}), 200);
  });

  ApiClient api({InMemoryDeviceAuthStore? store, String apiKey = ''}) {
    final auth = DeviceAuthService(
      registrationClient: ApiClient.unauthenticated(
          client: client, baseUrl: _base, apiKey: apiKey),
      store: store ?? InMemoryDeviceAuthStore(),
      legacyUserId: () async => _legacy,
    );
    return ApiClient(
        client: client, baseUrl: _base, apiKey: apiKey, auth: auth);
  }
}

ApiClient _plain(MockClientHandler handler,
        {Duration timeout = ApiClient.defaultTotalTimeout}) =>
    ApiClient(
      client: MockClient(handler),
      baseUrl: _base,
      timeout: timeout,
      auth: _StaticAuth(),
    );

class _StaticAuth implements AuthTokenProvider {
  @override
  Future<String> getToken() async => 't';
  @override
  Future<String> refreshToken() async => 't';
}

Future<AppException> _error(Future<void> Function() call) async {
  try {
    await call();
  } on AppException catch (e) {
    return e;
  }
  fail('expected AppException');
}

void main() {
  group('device JWT auth', () {
    setUp(() => DeviceAuthService.accountNotice.value = null);

    test('first run: sends legacy_user_id, stores user_id + device_secret',
        () async {
      final b = _Backend();
      final store = InMemoryDeviceAuthStore();
      final api = b.api(store: store, apiKey: 'secret');
      await api.getJson('/reminders');
      await api.getJson('/reminders');
      expect(b.registrations, 1);
      expect(b.registrationBodies.single, {'legacy_user_id': _legacy});
      expect(store.state.userId, _legacy);
      expect(store.state.deviceSecret, 'sec-$_legacy');
      expect(store.state.legacyClaimed, isTrue);
      expect(b.authHeaders, ['Bearer tok1', 'Bearer tok1']);
      expect(b.apiKeySeen, 'secret');
    });

    test('stored token is reused without registering', () async {
      final b = _Backend()..valid.add('saved');
      final api = b.api(
          store: InMemoryDeviceAuthStore(
              const DeviceAuthState(accessToken: 'saved')));
      await api.getJson('/users/me');
      expect(b.registrations, 0);
      expect(b.authHeaders.single, 'Bearer saved');
    });

    test('401 retry re-authenticates with user_id + secret, NOT legacy id',
        () async {
      final b = _Backend()..accounts['acc1'] = 'sec1';
      final store = InMemoryDeviceAuthStore(const DeviceAuthState(
        accessToken: 'revoked',
        userId: 'acc1',
        deviceSecret: 'sec1',
        legacyClaimed: true,
      ));
      final api = b.api(store: store);
      final res = await api.postJson('/assistant/message', {'message': 'x'});
      expect(res['ok'], isTrue);
      expect(b.registrationBodies.single,
          {'user_id': 'acc1', 'device_secret': 'sec1'});
      expect(b.authHeaders, ['Bearer revoked', 'Bearer tok1']);
      expect(store.state.userId, 'acc1'); // same account
      expect(store.state.deviceSecret, 'sec1'); // kept (null in reply)
      expect(store.state.accessToken, 'tok1');
      expect(DeviceAuthService.accountNotice.value, isNull);
    });

    test('expired token with stored secret → same account', () async {
      final b = _Backend()..accounts['acc1'] = 'sec1';
      final store = InMemoryDeviceAuthStore(DeviceAuthState(
        accessToken: 'old',
        expiresAt: DateTime.now().subtract(const Duration(minutes: 5)),
        userId: 'acc1',
        deviceSecret: 'sec1',
        legacyClaimed: true,
      ));
      await b.api(store: store).getJson('/users/me');
      expect(
          b.registrationBodies.single.containsKey('legacy_user_id'), isFalse);
      expect(store.state.userId, 'acc1');
    });

    test('invalid secret → wipe, one fresh registration, retry, notice',
        () async {
      final b = _Backend()..accounts['acc1'] = 'other';
      final store = InMemoryDeviceAuthStore(const DeviceAuthState(
        accessToken: 'revoked',
        userId: 'acc1',
        deviceSecret: 'stale',
        legacyClaimed: true,
      ));
      final res = await b.api(store: store).getJson('/reminders');
      expect(res['ok'], isTrue);
      expect(b.registrationBodies, [
        {'user_id': 'acc1', 'device_secret': 'stale'},
        <String, dynamic>{}, // fresh; legacy id NOT re-sent (already claimed)
      ]);
      expect(store.state.userId, 'u-2');
      expect(store.state.deviceSecret, 'sec-u-2');
      expect(b.authHeaders, ['Bearer revoked', 'Bearer tok2']);
      expect(DeviceAuthService.accountNotice.value,
          DeviceAuthService.accountResetMessage);
    });

    test('401 again after retry → friendly unauthorized error, no loop',
        () async {
      var registrations = 0;
      var calls = 0;
      final client = MockClient((req) async {
        if (req.url.path.endsWith('/auth/device')) {
          registrations++;
          return http.Response(jsonEncode({'access_token': 'bad'}), 200);
        }
        calls++;
        return http.Response('{"detail":"expired"}', 401);
      });
      final api = ApiClient(
        client: client,
        baseUrl: _base,
        auth: DeviceAuthService(
          registrationClient:
              ApiClient.unauthenticated(client: client, baseUrl: _base),
          store: InMemoryDeviceAuthStore(),
          legacyUserId: () async => _legacy,
        ),
      );
      final e = await _error(() => api.getJson('/reminders'));
      expect(e.type, AppErrorType.unauthorized);
      expect(e.message, contains('Serverə giriş alınmadı'));
      expect(calls, 2);
      expect(registrations, 2); // initial + one refresh
    });

    test('concurrent requests share one registration', () async {
      final b = _Backend();
      final api = b.api();
      await Future.wait([
        api.getJson('/a'),
        api.getJson('/b'),
        api.getJson('/c'),
      ]);
      expect(b.registrations, 1);
    });

    test('registration failure surfaces an Azerbaijani error', () async {
      final client = MockClient((req) async => http.Response('oops', 500));
      final api = ApiClient(
        client: client,
        baseUrl: _base,
        auth: DeviceAuthService(
          registrationClient:
              ApiClient.unauthenticated(client: client, baseUrl: _base),
          store: InMemoryDeviceAuthStore(),
          legacyUserId: () async => null,
        ),
      );
      final e = await _error(() => api.getJson('/reminders'));
      expect(e.message, contains('qeydiyyatdan keçirmək mümkün olmadı'));
    });
  });

  group('error mapping', () {
    test('422 validation list → detail shown', () async {
      final e = await _error(() => _plain((_) async => http.Response(
          jsonEncode({
            'detail': [
              {'msg': 'Field required'}
            ]
          }),
          422)).postJson('/x', {}));
      expect(e.type, AppErrorType.validation);
      expect(e.message, contains('Field required'));
    });

    test('4xx detail string shown; 404 typed', () async {
      final e = await _error(() => _plain((_) async =>
              _utf8(jsonEncode({'detail': 'Xatırlatma tapılmadı'}), 404))
          .getJson('/reminders/1'));
      expect(e.type, AppErrorType.notFound);
      expect(e.message, 'Xatırlatma tapılmadı');
    });

    test('413/415 typed with friendly fallbacks', () async {
      final big = await _error(
          () => _plain((_) async => http.Response('', 413)).postJson('/v', {}));
      expect(big.type, AppErrorType.payloadTooLarge);
      expect(big.message, contains('10 MB'));
      final mime = await _error(
          () => _plain((_) async => http.Response('', 415)).postJson('/v', {}));
      expect(mime.type, AppErrorType.unsupportedMedia);
    });

    test('5xx with HTML body → generic server message, no crash', () async {
      final e = await _error(() => _plain(
              (_) async => http.Response('<html>Bad Gateway</html>', 502))
          .getJson('/x'));
      expect(e.type, AppErrorType.server);
      expect(e.statusCode, 502);
      expect(e.message, contains('Serverdə xəta'));
    });

    test('2xx non-JSON body → badResponse, no crash', () async {
      final e = await _error(
          () => _plain((_) async => http.Response('not json', 200)).getJson('/x'));
      expect(e.type, AppErrorType.badResponse);
    });

    test('empty 204 body is fine', () async {
      await _plain((_) async => http.Response('', 204)).delete('/reminders/1');
    });

    test('SocketException → network', () async {
      final e = await _error(() => _plain(
          (_) async => throw const SocketException('no route')).getJson('/x'));
      expect(e.type, AppErrorType.network);
      expect(e.message, contains('İnternet'));
    });

    test('HandshakeException → tls', () async {
      final e = await _error(() =>
          _plain((_) async => throw const HandshakeException('bad cert'))
              .getJson('/x'));
      expect(e.type, AppErrorType.tls);
      expect(e.message, contains('HTTPS'));
    });

    test('ClientException → network', () async {
      final e = await _error(() =>
          _plain((_) async => throw http.ClientException('closed'))
              .getJson('/x'));
      expect(e.type, AppErrorType.network);
    });

    test('slow server → timeout', () async {
      final e = await _error(() => _plain((_) async {
            await Future<void>.delayed(const Duration(milliseconds: 200));
            return http.Response('{}', 200);
          }, timeout: const Duration(milliseconds: 20))
              .getJson('/x'));
      expect(e.type, AppErrorType.timeout);
    });
  });

  group('AppConfig.validateBaseUrl', () {
    test('release rejects http://', () {
      expect(
          AppConfig.validateBaseUrl('http://10.0.2.2:8000/api/v1', release: true),
          contains('https://'));
    });
    test('release accepts https://', () {
      expect(AppConfig.validateBaseUrl('https://api.yaxin.az/api/v1', release: true),
          isNull);
    });
    test('debug allows http://', () {
      expect(AppConfig.validateBaseUrl('http://10.0.2.2:8000/api/v1', release: false),
          isNull);
    });
    test('garbage URL rejected', () {
      expect(AppConfig.validateBaseUrl('not a url', release: false), isNotNull);
    });
  });
}
