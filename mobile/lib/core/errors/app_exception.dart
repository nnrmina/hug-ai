enum AppErrorType {
  network,
  timeout,
  tls,
  unauthorized,
  forbidden,
  notFound,
  conflict,
  validation,
  payloadTooLarge,
  unsupportedMedia,
  rateLimited,
  server,
  badResponse,
  config,
  unknown,
}

class AppException implements Exception {
  /// User-facing (Azerbaijani) message.
  final String message;

  final AppErrorType type;

  /// HTTP status code; null for network/timeout/TLS errors.
  final int? statusCode;

  /// Raw `detail` returned by the backend, if any.
  final String? detail;

  const AppException(
    this.message, {
    this.type = AppErrorType.unknown,
    this.statusCode,
    this.detail,
  });

  /// True when the request never got an HTTP answer (safe to retry later).
  bool get isConnectivity =>
      type == AppErrorType.network ||
      type == AppErrorType.timeout ||
      type == AppErrorType.tls;

  @override
  String toString() =>
      'AppException(type: $type, statusCode: $statusCode, message: $message)';
}
