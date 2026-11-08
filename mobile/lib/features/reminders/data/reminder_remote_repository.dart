import '../../../core/network/api_client.dart';
import '../domain/reminder_entity.dart';

class ReminderRemoteRepository {
  final ApiClient _apiClient;

  /// The backend derives the user from the JWT; no user_id is sent.
  ReminderRemoteRepository({ApiClient? apiClient})
      : _apiClient = apiClient ?? ApiClient();

  Future<List<ReminderEntity>> fetchReminders() async {
    final decoded = await _apiClient.getJson('/reminders');
    final list = decoded is List ? decoded : const [];
    return list
        .whereType<Map>()
        .map((e) => ReminderEntity.fromJson(Map<String, dynamic>.from(e)))
        .toList();
  }

  Future<ReminderEntity> createReminder({
    required String title,
    required DateTime scheduledAt,
    String timezone = 'Asia/Baku',
    String? description,
  }) async {
    final json = await _apiClient.postJson('/reminders', {
      'title': title,
      'scheduled_at': scheduledAt.toIso8601String(),
      'timezone': timezone,
      if (description != null) 'description': description,
    });
    return ReminderEntity.fromJson(json);
  }

  Future<ReminderEntity> updateStatus(String id, String status) async {
    final json = await _apiClient.patchJson(
      '/reminders/${Uri.encodeComponent(id)}',
      {'status': status},
    );
    return ReminderEntity.fromJson(json);
  }

  Future<void> deleteReminder(String id) async {
    await _apiClient.delete('/reminders/${Uri.encodeComponent(id)}');
  }
}
