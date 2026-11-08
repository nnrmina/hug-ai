class AssistantResponseModel {
  final String intent;
  final String response;
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

  factory AssistantResponseModel.fromJson(Map<String, dynamic> json) {
    return AssistantResponseModel(
      intent: json['intent'] as String? ?? 'UNKNOWN',
      response: json['response'] as String? ?? '',
      status: json['status'] as String? ?? 'needs_clarification',
      actionId: json['action_id'] as String?,
      actionData: json['action_data'] as Map<String, dynamic>?,
    );
  }
}

