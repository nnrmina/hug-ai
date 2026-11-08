class ReminderEntity {
  final String id;
  final String title;
  final DateTime scheduledAt;
  final String timezone;
  final String status;

  const ReminderEntity({
    required this.id,
    required this.title,
    required this.scheduledAt,
    this.timezone = 'Asia/Baku',
    this.status = 'pending',
  });

  factory ReminderEntity.fromJson(Map<String, dynamic> json) {
    return ReminderEntity(
      id: json['id'] as String,
      title: json['title'] as String,
      scheduledAt: DateTime.parse(json['scheduled_at'] as String),
      timezone: json['timezone'] as String? ?? 'Asia/Baku',
      status: json['status'] as String? ?? 'pending',
    );
  }
}

