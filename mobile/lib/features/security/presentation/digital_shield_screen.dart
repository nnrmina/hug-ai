import 'package:flutter/material.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';
import '../data/security_repository.dart';
import '../domain/security_analysis_entity.dart';

class DigitalShieldScreen extends StatefulWidget {
  final SecurityRepository? repository;

  const DigitalShieldScreen({super.key, this.repository});

  @override
  State<DigitalShieldScreen> createState() => _DigitalShieldScreenState();
}

class _DigitalShieldScreenState extends State<DigitalShieldScreen> {
  late final SecurityRepository _repository =
      widget.repository ?? SecurityRepository();
  final TextEditingController _controller = TextEditingController();

  bool _loading = false;
  String? _error;
  SecurityAnalysisEntity? _result;

  @override
  void dispose() {
    _controller.dispose();
    super.dispose();
  }

  Future<void> _analyze() async {
    final text = _controller.text.trim();
    if (text.isEmpty) {
      setState(() => _error = 'Zəhmət olmasa yoxlanacaq mesajı daxil edin.');
      return;
    }
    FocusScope.of(context).unfocus();
    setState(() {
      _loading = true;
      _error = null;
      _result = null;
    });
    try {
      final result = await _repository.analyzeMessage(text);
      if (!mounted) return;
      setState(() {
        _result = result;
        _loading = false;
      });
    } on AppException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    }
  }

  static ({Color color, String label, IconData icon}) _riskStyle(
      String level) {
    switch (level) {
      case 'high':
        return (
          color: AppTheme.dangerRed,
          label: 'YÜKSƏK RİSK',
          icon: Icons.gpp_bad_rounded,
        );
      case 'medium':
        return (
          color: AppTheme.warningAmber,
          label: 'ORTA RİSK',
          icon: Icons.gpp_maybe_rounded,
        );
      default:
        return (
          color: AppTheme.textAccentGreen,
          label: 'AŞAĞI RİSK',
          icon: Icons.gpp_good_rounded,
        );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Rəqəmsal Qalxan')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Text(
                'Şübhəli SMS və ya mesajı bura yapışdırın:',
                style: Theme.of(context).textTheme.titleLarge,
              ),
              const SizedBox(height: 12),
              TextField(
                controller: _controller,
                maxLines: 5,
                minLines: 3,
                style: const TextStyle(fontSize: 18),
                decoration: InputDecoration(
                  border: OutlineInputBorder(
                    borderRadius: BorderRadius.circular(16),
                  ),
                  hintText: 'Mesaj mətnini daxil edin...',
                  hintStyle: const TextStyle(fontSize: 18),
                ),
              ),
              const SizedBox(height: 16),
              AccessibleActionButton(
                label: 'Mesajı Yoxla',
                icon: Icons.security_rounded,
                backgroundColor: AppTheme.primaryGreen,
                onPressed: _loading ? null : _analyze,
              ),
              const SizedBox(height: 24),
              if (_loading) const Center(child: CircularProgressIndicator()),
              if (_error != null)
                Semantics(
                  liveRegion: true,
                  child: Text(
                    _error!,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w600,
                      color: AppTheme.dangerRed,
                    ),
                    textAlign: TextAlign.center,
                  ),
                ),
              if (_result != null) _buildResult(_result!),
            ],
          ),
        ),
      ),
    );
  }

  Widget _buildResult(SecurityAnalysisEntity r) {
    final style = _riskStyle(r.riskLevel);
    return Card(
      elevation: 3,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(18),
        side: BorderSide(color: style.color, width: 3),
      ),
      child: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Semantics(
              liveRegion: true,
              child: Row(
                children: [
                  Icon(style.icon, size: 40, color: style.color),
                  const SizedBox(width: 12),
                  Expanded(
                    child: Text(
                      '${style.label} (${r.riskScore}/100)',
                      style: TextStyle(
                        fontSize: 24,
                        fontWeight: FontWeight.bold,
                        color: style.color,
                      ),
                    ),
                  ),
                ],
              ),
            ),
            const SizedBox(height: 12),
            if (r.explanation.isNotEmpty)
              Text(r.explanation,
                  style: Theme.of(context).textTheme.bodyLarge),
            if (r.recommendation.isNotEmpty) ...[
              const SizedBox(height: 12),
              Text(
                r.recommendation,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }
}
