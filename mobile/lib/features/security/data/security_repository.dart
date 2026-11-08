import '../../../core/network/api_client.dart';
import '../domain/security_analysis_entity.dart';

class SecurityRepository {
  final ApiClient _apiClient;

  SecurityRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  Future<SecurityAnalysisEntity> analyzeMessage(String message) async {
    final json = await _apiClient.postJson(
      '/security/analyze',
      {'message': message},
    );
    return SecurityAnalysisEntity.fromJson(json);
  }
}

