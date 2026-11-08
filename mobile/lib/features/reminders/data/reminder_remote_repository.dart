import '../../../core/network/api_client.dart';
import '../domain/reminder_entity.dart';

class ReminderRemoteRepository {
  final ApiClient _apiClient;

  ReminderRemoteRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  Future<List<ReminderEntity>> fetchReminders() async {
    final list = await _apiClient.getJson('/reminders') as List<dynamic>;
    return list
        .map((e) => ReminderEntity.fromJson(e as Map<String, dynamic>))
        .toList();
  }
}

