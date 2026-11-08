import 'package:flutter/material.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';

class DigitalShieldScreen extends StatefulWidget {
  const DigitalShieldScreen({super.key});

  @override
  State<DigitalShieldScreen> createState() => _DigitalShieldScreenState();
}

class _DigitalShieldScreenState extends State<DigitalShieldScreen> {
  final TextEditingController _controller = TextEditingController(
    text:
        'Bank hesabınız bloklanıb. Linkə daxil olun və kart məlumatlarını yazın.',
  );

  String _riskLevel = 'YÜKSƏK RİSK (87/100)';
  String _explanation =
      'Bu mesajda təcili hərəkət tələbi (urgency), şübhəli keçid (suspicious_link) və kart məlumatlarının istənilməsi (credential_request) aşkar edildi.';
  String _recommendation =
      'Tövsiyə: Keçidə daxil olmayın və şifrə/kart məlumatlarınızı heç kimlə paylaşmayın.';

  void _analyzeLocalPreview() {
    final text = _controller.text.toLowerCase();
    setState(() {
      if (text.contains('bloklanıb') ||
          text.contains('kart') ||
          text.contains('link') ||
          text.contains('şifrə')) {
        _riskLevel = 'YÜKSƏK RİSK';
        _explanation =
            'Bu mesajda yüksək dələduzluq əlamətləri var: bank adından istifadə, təcili qorxutma və kart məlumatı tələbi.';
        _recommendation =
            'Tövsiyə: Keçidə (linkə) daxil olmayın və rəsmi bank nömrəsinə birbaşa zəng edin.';
      } else {
        _riskLevel = 'AŞAĞI RİSK';
        _explanation = 'Mesajda açıq fırıldaqçılıq əlaməti aşkar edilmədi.';
        _recommendation =
            'Tövsiyə: Yenə də şəxsi şifrələrinizi SMS-lə göndərməyin.';
      }
    });
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Rəqəmsal Qalxan (Digital Shield)')),
      body: SingleChildScrollView(
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
              maxLines: 4,
              style: const TextStyle(fontSize: 18),
              decoration: InputDecoration(
                border: OutlineInputBorder(
                  borderRadius: BorderRadius.circular(16),
                ),
                hintText: 'Mesaj mətnini daxil edin...',
              ),
            ),
            const SizedBox(height: 16),
            AccessibleActionButton(
              label: 'Mesajı Yoxla',
              icon: Icons.security_rounded,
              backgroundColor: AppTheme.primaryBlue,
              onPressed: _analyzeLocalPreview,
            ),
            const SizedBox(height: 24),
            Card(
              elevation: 3,
              shape: RoundedRectangleBorder(
                borderRadius: BorderRadius.circular(18),
              ),
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      _riskLevel,
                      style: const TextStyle(
                        fontSize: 22,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.dangerRed,
                      ),
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _explanation,
                      style: Theme.of(context).textTheme.bodyLarge,
                    ),
                    const SizedBox(height: 12),
                    Text(
                      _recommendation,
                      style: const TextStyle(
                        fontSize: 18,
                        fontWeight: FontWeight.w600,
                      ),
                    ),
                  ],
                ),
              ),
            ),
          ],
        ),
      ),
    );
  }
}

