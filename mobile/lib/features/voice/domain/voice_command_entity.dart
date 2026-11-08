class VoiceCommandEntity {
  final String transcript;
  final String locale;
  final DateTime recordedAt;

  const VoiceCommandEntity({
    required this.transcript,
    this.locale = 'az-AZ',
    required this.recordedAt,
  });
}

