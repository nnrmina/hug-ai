import 'dart:convert';
import 'package:http/http.dart' as http;
import '../config/app_config.dart';
import '../errors/app_exception.dart';

class ApiClient {
  final http.Client _client;
  final String baseUrl;

  ApiClient({http.Client? client, this.baseUrl = AppConfig.apiBaseUrl})
      : _client = client ?? http.Client();

  Future<Map<String, dynamic>> postJson(
    String path,
    Map<String, dynamic> body,
  ) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await _client.post(
      uri,
      headers: const {'Content-Type': 'application/json; charset=utf-8'},
      body: jsonEncode(body),
    );
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(utf8.decode(response.bodyBytes)) as Map<String, dynamic>;
    }
    throw AppException(
      'Server xətası baş verdi (${response.statusCode})',
      statusCode: response.statusCode,
    );
  }

  Future<dynamic> getJson(String path) async {
    final uri = Uri.parse('$baseUrl$path');
    final response = await _client.get(uri);
    if (response.statusCode >= 200 && response.statusCode < 300) {
      return jsonDecode(utf8.decode(response.bodyBytes));
    }
    throw AppException(
      'Məlumat alına bilmədi (${response.statusCode})',
      statusCode: response.statusCode,
    );
  }
}

