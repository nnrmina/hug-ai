class AssistantResponseModel {
  final String intent;
  final String response;

  /// completed | needs_confirmation | needs_clarification | rejected | cancelled
  final String status;
  final String? actionId;
  final Map<String, dynamic>? actionData;

  const AssistantResponseModel({
    required this.intent,
    required this.response,
    required this.status,
    this.actionId,
    this.actionData,
  });

  bool get needsConfirmation => status == 'needs_confirmation';

  factory AssistantResponseModel.fromJson(Map<String, dynamic> json) {
    final data = json['action_data'];
    return AssistantResponseModel(
      intent: json['intent']?.toString() ?? 'UNKNOWN',
      response: json['response']?.toString() ?? '',
      status: json['status']?.toString() ?? 'needs_clarification',
      actionId: json['action_id']?.toString(),
      actionData: data is Map ? Map<String, dynamic>.from(data) : null,
    );
  }

  /// Names to look up locally: `contact_alias` then `search_candidates`.
  List<String> get contactQueries {
    final out = <String>[];
    final alias = actionData?['contact_alias'];
    if (alias is String && alias.trim().isNotEmpty) out.add(alias.trim());
    final candidates = actionData?['search_candidates'];
    if (candidates is List) {
      for (final c in candidates) {
        final s = c?.toString().trim() ?? '';
        if (s.isNotEmpty && !out.contains(s)) out.add(s);
      }
    }
    return out;
  }
}
