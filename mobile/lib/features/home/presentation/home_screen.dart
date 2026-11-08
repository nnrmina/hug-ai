import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../app/routes.dart';
import '../../contacts/data/local_contact_matcher.dart';
import '../../voice/data/speech_engine_service.dart';
import '../../voice/data/voice_assistant_repository.dart';
import '../widgets/big_microphone_button.dart';

class HomeScreen extends StatefulWidget {
  const HomeScreen({super.key});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> {
  final SpeechEngineService _speechService = SpeechEngineService();
  final VoiceAssistantRepository _assistantRepo = VoiceAssistantRepository();
  final LocalContactMatcher _contactMatcher = LocalContactMatcher();

  bool _isListening = true;
  String _statusSubtitle = '';
  bool _isExecuting = false;

  @override
  void initState() {
    super.initState();
    // AUTO-START ON LAUNCH: Yaşlı insan tətbiqi açan kimi dərhal avtomatik dinləməyə başlayır
    WidgetsBinding.instance.addPostFrameCallback((_) {
      _startContinuousAutoListening();
    });
  }

  Future<void> _startContinuousAutoListening() async {
    if (_isExecuting) return;
    setState(() {
      _isListening = true;
    });

    await _speechService.startListening(
      onResult: (words) async {
        final text = words.trim();
        if (text.isNotEmpty) {
          setState(() {
            _statusSubtitle = '"$text"';
          });
          final lower = text.toLowerCase();
          if (lower.contains('zəng') ||
              lower.contains('yığ') ||
              lower.contains('mama') ||
              lower.contains('almaz')) {
            await _executeAiAgent(text);
          }
        }
      },
    );
  }

  Future<void> _executeAiAgent(String rawCommand) async {
    final command = rawCommand.trim();
    if (command.isEmpty || _isExecuting) return;

    _isExecuting = true;
    await _speechService.stopListening();
    setState(() {
      _isListening = false;
      _statusSubtitle = '"$command"';
    });

    String targetAlias = command;
    try {
      final apiRes = await _assistantRepo.sendCommand(command);
      if (apiRes.actionData != null &&
          apiRes.actionData!['contact_alias'] != null) {
        targetAlias = apiRes.actionData!['contact_alias'].toString();
      }
    } catch (_) {
      targetAlias = LocalContactMatcher.normalizeAzerbaijaniName(command);
    }

    final matched = await _contactMatcher.searchDeviceContacts(targetAlias);
    if (matched != null) {
      setState(() {
        _statusSubtitle = '${matched.displayName} tapıldı · Zəng edilir...';
      });
      await _speechService
          .speak('${matched.displayName} tapıldı. Zəng edilir.');

      final telUri = Uri(scheme: 'tel', path: matched.phoneNumber);
      if (await canLaunchUrl(telUri)) {
        await launchUrl(telUri);
      } else if (mounted) {
        Navigator.pushNamed(
          context,
          AppRoutes.contactConfirmation,
          arguments: matched,
        );
      }
    } else {
      setState(() {
        _statusSubtitle = 'Kontaktlarda "$targetAlias" tapılmadı.';
      });
      _isExecuting = false;
      _startContinuousAutoListening();
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: Padding(
          padding: const EdgeInsets.symmetric(horizontal: 22.0, vertical: 14.0),
          child: Column(
            mainAxisAlignment: MainAxisAlignment.spaceBetween,
            children: [
              // Top Minimal Bar (Menu | ✦ HUG | Edit)
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _CircleTopButton(
                    icon: Icons.notes_rounded,
                    onTap: () => Navigator.pushNamed(
                        context, AppRoutes.contactConfirmation),
                  ),
                  Container(
                    padding: const EdgeInsets.symmetric(
                        horizontal: 20, vertical: 10),
                    decoration: BoxDecoration(
                      color: Colors.white.withOpacity(0.85),
                      borderRadius: BorderRadius.circular(26),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome,
                            size: 16, color: Color(0xFF1C241E)),
                        SizedBox(width: 6),
                        Text(
                          'HUG',
                          style: TextStyle(
                            fontSize: 13,
                            fontWeight: FontWeight.w600,
                            color: Color(0xFF1C241E),
                          ),
                        ),
                      ],
                    ),
                  ),
                  _CircleTopButton(
                    icon: Icons.edit_outlined,
                    onTap: () =>
                        Navigator.pushNamed(context, AppRoutes.settings),
                  ),
                ],
              ),

              // Centered Headline
              Column(
                children: [
                  RichText(
                    textAlign: TextAlign.center,
                    text: const TextSpan(
                      style: TextStyle(
                        fontSize: 27,
                        fontWeight: FontWeight.w600,
                        height: 1.28,
                        color: Color(0xFF111812),
                      ),
                      children: [
                        TextSpan(text: 'Bu gün sizə necə '),
                        TextSpan(
                          text: 'kömək\n',
                          style: TextStyle(
                            color: Color(0xFF79E024),
                            fontWeight: FontWeight.w700,
                          ),
                        ),
                        TextSpan(text: 'edə bilərəm?'),
                      ],
                    ),
                  ),
                  if (_statusSubtitle.isNotEmpty) ...[
                    const SizedBox(height: 10),
                    Text(
                      _statusSubtitle,
                      style: Theme.of(context).textTheme.bodyMedium,
                      textAlign: TextAlign.center,
                    ),
                  ],
                ],
              ),

              // 3D Glossy Green AI Orb (Always active)
              BigMicrophoneButton(
                isListening: _isListening,
                onTap: _startContinuousAutoListening,
              ),

              const SizedBox(height: 60),
            ],
          ),
        ),
      ),
    );
  }
}

class _CircleTopButton extends StatelessWidget {
  final IconData icon;
  final VoidCallback onTap;

  const _CircleTopButton({required this.icon, required this.onTap});

  @override
  Widget build(BuildContext context) {
    return GestureDetector(
      onTap: onTap,
      child: Container(
        width: 44,
        height: 44,
        decoration: BoxDecoration(
          color: Colors.white.withOpacity(0.8),
          shape: BoxShape.circle,
        ),
        child: Icon(icon, size: 20, color: const Color(0xFF1C241E)),
      ),
    );
  }
}
