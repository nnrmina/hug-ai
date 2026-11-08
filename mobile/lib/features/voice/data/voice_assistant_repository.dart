import '../../../core/network/api_client.dart';
import '../../../shared/models/assistant_response_model.dart';

class VoiceAssistantRepository {
  final ApiClient _apiClient;

  VoiceAssistantRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  Future<AssistantResponseModel> sendCommand(String message) async {
    final json = await _apiClient.postJson(
      '/assistant/message',
      {'message': message},
    );
    return AssistantResponseModel.fromJson(json);
  }

  Future<Map<String, dynamic>> confirmAction(String actionId) async {
    return _apiClient.postJson('/assistant/confirm/$actionId', {});
  }

  Future<Map<String, dynamic>> cancelAction(String actionId) async {
    return _apiClient.postJson('/assistant/cancel/$actionId', {});
  }
}

