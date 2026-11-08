class ReminderEntity {
  final String id;
  final String title;
  final String? description;
  final DateTime scheduledAt;
  final String timezone;
  final String status;

  const ReminderEntity({
    required this.id,
    required this.title,
    required this.scheduledAt,
    this.description,
    this.timezone = 'Asia/Baku',
    this.status = 'pending',
  });

  factory ReminderEntity.fromJson(Map<String, dynamic> json) {
    final rawDate = json['scheduled_at']?.toString();
    return ReminderEntity(
      id: json['id']?.toString() ?? '',
      title: json['title']?.toString() ?? '',
      description: json['description']?.toString(),
      scheduledAt: (rawDate != null ? DateTime.tryParse(rawDate) : null) ??
          DateTime.fromMillisecondsSinceEpoch(0),
      timezone: json['timezone']?.toString() ?? 'Asia/Baku',
      status: json['status']?.toString() ?? 'pending',
    );
  }
}
