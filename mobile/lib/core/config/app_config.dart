import 'package:flutter/foundation.dart';

/// Build-time configuration, supplied with `--dart-define`.
///
/// Examples:
///   Android emulator (default; the host machine is reachable as 10.0.2.2):
///     flutter run
///   Physical device on the same Wi-Fi (also add the IP to
///   android/app/src/debug/res/xml/network_security_config.xml):
///     flutter run --dart-define=API_BASE_URL=http://192.168.1.20:8000/api/v1
///   Release (HTTPS is mandatory - see [configError]):
///     flutter build apk --release
///       --dart-define=API_BASE_URL=https://api.example.az/api/v1
///       --dart-define=API_KEY=xxxxx
class AppConfig {
  static const String appName = 'YAXIN AI';
  static const String defaultLocale = 'az_AZ';
  static const String defaultTimezone = 'Asia/Baku';

  /// Backend base URL including the `/api/v1` prefix.
  /// Default `10.0.2.2` is the Android emulator alias for the host localhost
  /// and only works in debug builds.
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );

  /// Optional API key sent as `X-API-Key`. Empty means no header is sent.
  static const String apiKey = String.fromEnvironment('API_KEY');

  /// Returns a problem description if [baseUrl] is not allowed in this build
  /// mode, otherwise null. Release builds must use HTTPS.
  static String? validateBaseUrl(String baseUrl, {bool release = kReleaseMode}) {
    final uri = Uri.tryParse(baseUrl);
    if (uri == null || !uri.hasScheme || uri.host.isEmpty) {
      return 'API_BASE_URL düzgün deyil: "$baseUrl"';
    }
    if (release && uri.scheme != 'https') {
      return 'Release versiyasında API_BASE_URL https:// ilə başlamalıdır '
          '(indiki: "$baseUrl"). --dart-define=API_BASE_URL=https://... ilə yenidən yığın.';
    }
    if (uri.scheme != 'https' && uri.scheme != 'http') {
      return 'API_BASE_URL yalnız http və ya https ola bilər: "$baseUrl"';
    }
    return null;
  }

  static String? get configError => validateBaseUrl(apiBaseUrl);
}
