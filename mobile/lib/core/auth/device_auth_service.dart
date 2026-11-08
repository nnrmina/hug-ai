import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../errors/app_exception.dart';
import '../identity/user_identity_service.dart';
import '../network/api_client.dart';

/// Supplies the bearer token used by [ApiClient].
abstract class AuthTokenProvider {
  /// Returns a valid token, (re-)authenticating the device first if needed.
  Future<String> getToken();

  /// Discards the access token and authenticates again (after a 401).
  Future<String> refreshToken();
}

/// Everything persisted for device auth.
class DeviceAuthState {
  final String? accessToken;
  final DateTime? expiresAt;

  /// Server account id + secret: re-authenticate into the SAME account.
  final String? userId;
  final String? deviceSecret;

  /// True once the install UUID was offered as `legacy_user_id`. It can be
  /// claimed only once, so it is never sent again afterwards.
  final bool legacyClaimed;

  const DeviceAuthState({
    this.accessToken,
    this.expiresAt,
    this.userId,
    this.deviceSecret,
    this.legacyClaimed = false,
  });

  bool get hasCredentials =>
      (userId?.isNotEmpty ?? false) && (deviceSecret?.isNotEmpty ?? false);

  DeviceAuthState copyWith({
    String? accessToken,
    DateTime? expiresAt,
    String? userId,
    String? deviceSecret,
    bool? legacyClaimed,
    bool clearToken = false,
    bool clearCredentials = false,
  }) {
    return DeviceAuthState(
      accessToken: clearToken ? null : (accessToken ?? this.accessToken),
      expiresAt: clearToken ? null : (expiresAt ?? this.expiresAt),
      userId: clearCredentials ? null : (userId ?? this.userId),
      deviceSecret:
          clearCredentials ? null : (deviceSecret ?? this.deviceSecret),
      legacyClaimed: legacyClaimed ?? this.legacyClaimed,
    );
  }
}

abstract class DeviceAuthStore {
  Future<DeviceAuthState> read();
  Future<void> write(DeviceAuthState state);
}

/// shared_preferences-backed store (MVP; no extra native dependency).
/// TODO(security): move the device secret to Android Keystore-backed storage
/// (e.g. flutter_secure_storage) before production.
class SharedPrefsDeviceAuthStore implements DeviceAuthStore {
  static const _kToken = 'yaxin_access_token';
  static const _kExpires = 'yaxin_access_token_expires_at';
  static const _kUser = 'yaxin_server_user_id';
  static const _kSecret = 'yaxin_device_secret';
  static const _kLegacyClaimed = 'yaxin_legacy_claimed';

  @override
  Future<DeviceAuthState> read() async {
    final p = await SharedPreferences.getInstance();
    final exp = p.getString(_kExpires);
    return DeviceAuthState(
      accessToken: p.getString(_kToken),
      expiresAt: exp == null ? null : DateTime.tryParse(exp),
      userId: p.getString(_kUser),
      deviceSecret: p.getString(_kSecret),
      legacyClaimed: p.getBool(_kLegacyClaimed) ?? false,
    );
  }

  @override
  Future<void> write(DeviceAuthState s) async {
    final p = await SharedPreferences.getInstance();
    Future<void> put(String key, String? value) =>
        value == null ? p.remove(key) : p.setString(key, value);
    await put(_kToken, s.accessToken);
    await put(_kExpires, s.expiresAt?.toIso8601String());
    await put(_kUser, s.userId);
    await put(_kSecret, s.deviceSecret);
    await p.setBool(_kLegacyClaimed, s.legacyClaimed);
  }
}

class InMemoryDeviceAuthStore implements DeviceAuthStore {
  DeviceAuthState state;

  InMemoryDeviceAuthStore([this.state = const DeviceAuthState()]);

  @override
  Future<DeviceAuthState> read() async => state;

  @override
  Future<void> write(DeviceAuthState s) async => state = s;
}

/// Anonymous per-device accounts: POST /auth/device → JWT.
///
/// * First run: `{legacy_user_id}` (keeps pre-JWT data); the response's
///   `user_id` + `device_secret` are stored.
/// * Every later registration: `{user_id, device_secret}` → same account.
/// * Secret rejected (401): credentials are wiped, one fresh registration is
///   made and [accountNotice] tells the user old data could not be restored.
class DeviceAuthService implements AuthTokenProvider {
  static DeviceAuthService? _shared;
  static DeviceAuthService get shared => _shared ??= DeviceAuthService();

  /// User-facing notice (Azerbaijani) — e.g. shown as a banner on Home.
  static final ValueNotifier<String?> accountNotice = ValueNotifier(null);

  static const String accountResetMessage =
      'Cihazın hesabı bərpa oluna bilmədi. Yeni hesab yaradıldı — serverdə '
      'saxlanmış köhnə xatırlatmalarınız bu telefonda görünməyəcək.';

  final ApiClient _client;
  final DeviceAuthStore _store;
  final Future<String?> Function() _legacyUserId;

  /// Refresh this long before the server-side expiry.
  static const Duration _expirySkew = Duration(minutes: 1);

  Future<String>? _inflight;
  DeviceAuthState? _cache;

  DeviceAuthService({
    ApiClient? registrationClient,
    DeviceAuthStore? store,
    Future<String?> Function()? legacyUserId,
  })  : _client = registrationClient ?? ApiClient.unauthenticated(),
        _store = store ?? SharedPrefsDeviceAuthStore(),
        _legacyUserId = legacyUserId ?? _defaultLegacyUserId;

  static Future<String?> _defaultLegacyUserId() async {
    try {
      return await UserIdentityService.getUserId();
    } catch (_) {
      return null;
    }
  }

  Future<DeviceAuthState> _read() async {
    if (_cache != null) return _cache!;
    try {
      return _cache = await _store.read();
    } catch (_) {
      return _cache = const DeviceAuthState();
    }
  }

  Future<void> _save(DeviceAuthState s) async {
    _cache = s;
    try {
      await _store.write(s);
    } catch (_) {
      // Still usable for this session even if it could not be persisted.
    }
  }

  @override
  Future<String> getToken() async {
    final s = await _read();
    final token = s.accessToken;
    if (token != null && token.isNotEmpty && !_isExpired(s)) return token;
    return _authenticate();
  }

  @override
  Future<String> refreshToken() async {
    await _save((await _read()).copyWith(clearToken: true));
    return _authenticate();
  }

  bool _isExpired(DeviceAuthState s) =>
      s.expiresAt != null &&
      DateTime.now()
          .toUtc()
          .isAfter(s.expiresAt!.toUtc().subtract(_expirySkew));

  /// Concurrent callers share one request.
  Future<String> _authenticate() =>
      _inflight ??= _doAuthenticate().whenComplete(() => _inflight = null);

  Future<String> _doAuthenticate() async {
    var state = await _read();

    if (state.hasCredentials) {
      try {
        final json = await _client.postJson('/auth/device', {
          'user_id': state.userId,
          'device_secret': state.deviceSecret,
        });
        return await _accept(json, state);
      } on AppException catch (e) {
        if (e.statusCode != 401) throw _wrap(e);
        // Secret unknown/invalid → start over with a fresh account (once).
        state = state.copyWith(clearToken: true, clearCredentials: true);
        await _save(state);
        accountNotice.value = accountResetMessage;
      }
    }

    // First registration (or fresh one after a rejected secret).
    final legacy = state.legacyClaimed ? null : await _legacyUserId();
    final Map<String, dynamic> json;
    try {
      json = await _client.postJson('/auth/device', {
        if (legacy != null && legacy.isNotEmpty) 'legacy_user_id': legacy,
      });
    } on AppException catch (e) {
      throw _wrap(e);
    }
    return _accept(json, state.copyWith(legacyClaimed: true));
  }

  Future<String> _accept(Map<String, dynamic> json, DeviceAuthState base) async {
    final token = json['access_token']?.toString() ?? '';
    if (token.isEmpty) {
      throw const AppException(
        'Serverdən giriş açarı alınmadı. Bir az sonra yenidən cəhd edin.',
        type: AppErrorType.badResponse,
      );
    }
    final exp = json['expires_at']?.toString();
    final secret = json['device_secret']?.toString();
    final userId = json['user_id']?.toString();
    await _save(base.copyWith(
      accessToken: token,
      expiresAt: exp == null ? null : DateTime.tryParse(exp),
      userId: userId,
      // Secret is only returned for a NEW binding; otherwise keep ours.
      deviceSecret: (secret != null && secret.isNotEmpty) ? secret : null,
    ));
    return token;
  }

  static AppException _wrap(AppException e) {
    if (e.isConnectivity) return e;
    return AppException(
      'Cihazı serverdə qeydiyyatdan keçirmək mümkün olmadı. Bir az sonra yenidən cəhd edin.',
      type: AppErrorType.unauthorized,
      statusCode: e.statusCode,
      detail: e.detail,
    );
  }
}
