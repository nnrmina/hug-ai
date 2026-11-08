class SecurityAnalysisEntity {
  final String analysisId;
  final String riskLevel;
  final int riskScore;
  final List<String> indicators;
  final String explanation;
  final String recommendation;

  const SecurityAnalysisEntity({
    required this.analysisId,
    required this.riskLevel,
    required this.riskScore,
    required this.indicators,
    required this.explanation,
    required this.recommendation,
  });

  factory SecurityAnalysisEntity.fromJson(Map<String, dynamic> json) {
    return SecurityAnalysisEntity(
      analysisId: json['analysis_id'] as String? ?? '',
      riskLevel: json['risk_level'] as String? ?? 'low',
      riskScore: json['risk_score'] as int? ?? 0,
      indicators: (json['indicators'] as List<dynamic>? ?? [])
          .map((e) => e.toString())
          .toList(),
      explanation: json['explanation'] as String? ?? '',
      recommendation: json['recommendation'] as String? ?? '',
    );
  }
}

