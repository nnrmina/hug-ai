import 'package:flutter/material.dart';
import '../../../app/routes.dart';
import '../../../core/constants/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../../contacts/data/local_contact_matcher.dart';
import '../../contacts/domain/local_contact_alias.dart';
import '../../home/widgets/big_microphone_button.dart';
import '../data/speech_engine_service.dart';
import '../data/voice_assistant_repository.dart';

class VoiceAssistantScreen extends StatefulWidget {
  const VoiceAssistantScreen({super.key});

  @override
  State<VoiceAssistantScreen> createState() => _VoiceAssistantScreenState();
}

class _VoiceAssistantScreenState extends State<VoiceAssistantScreen> {
  final VoiceAssistantRepository _repository = VoiceAssistantRepository();
  final SpeechEngineService _speechService = SpeechEngineService();
  final LocalContactMatcher _contactMatcher = LocalContactMatcher();
  final TextEditingController _textController =
      TextEditingController(text: 'Qızıma zəng et');

  bool _isListening = false;
  bool _isLoading = false;
  String _intent = 'MAKE_CALL';
  String _assistantReply =
      '"qızım" (Aysel Ibrahimova) kontaktına zəng etmək istəyirsiniz?';
  bool _needsConfirmation = true;
  String? _activeActionId;
  LocalContactAlias? _matchedContact;

  @override
  void initState() {
    super.initState();
    _matchedContact = _contactMatcher.findByAliasOrName('qızım');
  }

  Future<void> _sendCommand(String commandText) async {
    if (commandText.trim().isEmpty) return;
    setState(() {
      _isLoading = true;
    });

    try {
      final result = await _repository.sendCommand(commandText.trim());
      LocalContactAlias? matched;
      if (result.intent == 'MAKE_CALL' ||
          result.intent == 'SEND_VOICE_MESSAGE') {
        final alias =
            result.actionData?['contact_alias']?.toString() ?? 'qızım';
        matched = _contactMatcher.findByAliasOrName(alias);
      }

      setState(() {
        _intent = result.intent;
        _assistantReply = result.response;
        _needsConfirmation = result.status == 'needs_confirmation';
        _activeActionId = result.actionId;
        _matchedContact = matched;
        _isLoading = false;
      });
      await _speechService.speak(result.response);
    } catch (_) {
      // Offline / local fallback
      final lower = commandText.toLowerCase();
      setState(() {
        _isLoading = false;
        if (lower.contains('zəng')) {
          _intent = 'MAKE_CALL';
          _matchedContact = _contactMatcher.findByAliasOrName('qızım');
          _assistantReply =
              '"qızım" (${_matchedContact?.displayName}) kontaktına zəng etmək istəyirsiniz?';
          _needsConfirmation = true;
        } else if (lower.contains('xatırlat') || lower.contains('oyat')) {
          _intent = 'CREATE_REMINDER';
          _matchedContact = null;
          _assistantReply =
              '"$commandText" üçün xatırlatma yaradılsın?';
          _needsConfirmation = true;
        } else {
          _intent = 'ANALYZE_MESSAGE';
          _matchedContact = null;
          _assistantReply = 'Əmriniz emal edildi.';
          _needsConfirmation = false;
        }
      });
    }
  }

  Future<void> _confirmAction() async {
    if (_activeActionId != null) {
      try {
        await _repository.confirmAction(_activeActionId!);
      } catch (_) {}
    }
    if (!mounted) return;
    if (_intent == 'MAKE_CALL') {
      Navigator.pushNamed(context, AppRoutes.contactConfirmation);
    } else {
      setState(() {
        _needsConfirmation = false;
        _assistantReply = 'Əməliyyat təsdiqləndi və icra olundu.';
      });
    }
  }

  Future<void> _cancelAction() async {
    if (_activeActionId != null) {
      try {
        await _repository.cancelAction(_activeActionId!);
      } catch (_) {}
    }
    setState(() {
      _needsConfirmation = false;
      _assistantReply = 'Əməliyyat istifadəçi tərəfindən ləğv edildi.';
    });
  }

  Future<void> _toggleListening() async {
    if (_isListening) {
      await _speechService.stopListening();
      setState(() => _isListening = false);
      await _sendCommand(_textController.text);
    } else {
      setState(() => _isListening = true);
      await _speechService.startListening(
        onResult: (words) {
          setState(() {
            _textController.text = words;
          });
        },
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Səsli Köməkçi (az-AZ)')),
      body: Padding(
        padding: const EdgeInsets.all(20.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
          children: [
            Row(
              children: [
                Expanded(
                  child: TextField(
                    controller: _textController,
                    style: const TextStyle(fontSize: 18),
                    decoration: InputDecoration(
                      hintText: 'Əmrinizi yazın və ya danışın...',
                      border: OutlineInputBorder(
                        borderRadius: BorderRadius.circular(14),
                      ),
                    ),
                    onSubmitted: _sendCommand,
                  ),
                ),
                const SizedBox(width: 8),
                ElevatedButton(
                  style: ElevatedButton.styleFrom(
                    backgroundColor: AppTheme.primaryBlue,
                    foregroundColor: Colors.white,
                    minimumSize: const Size(64, 56),
                  ),
                  onPressed: () => _sendCommand(_textController.text),
                  child: const Icon(Icons.send_rounded),
                ),
              ],
            ),
            Card(
              elevation: 2,
              child: Padding(
                padding: const EdgeInsets.all(20.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Niyyət (Intent): $_intent',
                      style: const TextStyle(
                        fontSize: 15,
                        fontWeight: FontWeight.bold,
                        color: AppTheme.primaryBlue,
                      ),
                    ),
                    const Divider(height: 24),
                    const Text(
                      'YAXIN AI cavabı:',
                      style: TextStyle(fontSize: 16, color: Colors.black54),
                    ),
                    const SizedBox(height: 8),
                    if (_isLoading)
                      const Center(child: CircularProgressIndicator())
                    else
                      Text(
                        _assistantReply,
                        style: Theme.of(context).textTheme.bodyLarge,
                      ),
                    if (_matchedContact != null) ...[
                      const SizedBox(height: 12),
                      Container(
                        padding: const EdgeInsets.all(12),
                        decoration: BoxDecoration(
                          color: Colors.green.withOpacity(0.1),
                          borderRadius: BorderRadius.circular(12),
                        ),
                        child: Row(
                          children: [
                            const Icon(Icons.contact_phone,
                                color: AppTheme.confirmGreen),
                            const SizedBox(width: 10),
                            Expanded(
                              child: Text(
                                '${_matchedContact!.displayName} (${_matchedContact!.phoneNumber})',
                                style: const TextStyle(
                                  fontSize: 18,
                                  fontWeight: FontWeight.w600,
                                ),
                              ),
                            ),
                          ],
                        ),
                      ),
                    ],
                  ],
                ),
              ),
            ),
            BigMicrophoneButton(
              isListening: _isListening,
              onTap: _toggleListening,
            ),
            if (_needsConfirmation)
              Row(
                children: [
                  Expanded(
                    child: SizedBox(
                      height: 60,
                      child: OutlinedButton(
                        onPressed: _cancelAction,
                        child: const Text(
                          AppStrings.cancelButton,
                          style: TextStyle(fontSize: 18),
                        ),
                      ),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: SizedBox(
                      height: 60,
                      child: ElevatedButton(
                        style: ElevatedButton.styleFrom(
                          backgroundColor: AppTheme.confirmGreen,
                          foregroundColor: Colors.white,
                        ),
                        onPressed: _confirmAction,
                        child: const Text(
                          AppStrings.confirmButton,
                          style: TextStyle(fontSize: 18),
                        ),
                      ),
                    ),
                  ),
                ],
              ),
          ],
        ),
      ),
    );
  }
}
