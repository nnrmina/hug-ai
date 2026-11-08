import '../../../core/errors/app_exception.dart';
import '../../../core/network/api_client.dart';
import '../../../shared/models/assistant_response_model.dart';

class VoiceAssistantRepository {
  final ApiClient _apiClient;

  /// The backend derives the user from the JWT; no user_id is sent.
  VoiceAssistantRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  Future<AssistantResponseModel> sendCommand(String message) async {
    final json = await _apiClient.postJson(
      '/assistant/message',
      {'message': message},
    );
    return AssistantResponseModel.fromJson(json);
  }

  /// Throws [AppException] with a friendly Azerbaijani message on 404/409.
  Future<AssistantResponseModel> confirmAction(String actionId) async {
    try {
      final json = await _apiClient.postJson(
          '/assistant/confirm/${Uri.encodeComponent(actionId)}', {});
      return AssistantResponseModel.fromJson(json);
    } on AppException catch (e) {
      throw _friendly(e);
    }
  }

  Future<AssistantResponseModel> cancelAction(String actionId) async {
    try {
      final json = await _apiClient.postJson(
          '/assistant/cancel/${Uri.encodeComponent(actionId)}', {});
      return AssistantResponseModel.fromJson(json);
    } on AppException catch (e) {
      throw _friendly(e);
    }
  }

  static AppException _friendly(AppException e) {
    switch (e.statusCode) {
      case 404:
        return AppException(
          'Bu əmrin vaxtı bitib və ya tapılmadı. Zəhmət olmasa əmri yenidən deyin.',
          statusCode: 404,
          detail: e.detail,
        );
      case 409:
        return AppException(
          'Bu əmr artıq icra olunub və ya ləğv edilib. Zəhmət olmasa yenidən deyin.',
          statusCode: 409,
          detail: e.detail,
        );
      default:
        return e;
    }
  }
}
