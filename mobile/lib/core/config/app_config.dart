class AppConfig {
  static const String appName = 'YAXIN AI';
  static const String defaultLocale = 'az_AZ';
  static const String defaultTimezone = 'Asia/Baku';

  /// Android emulator localhost alias (`10.0.2.2`) or LAN IP for physical device
  static const String apiBaseUrl = String.fromEnvironment(
    'API_BASE_URL',
    defaultValue: 'http://10.0.2.2:8000/api/v1',
  );
}

