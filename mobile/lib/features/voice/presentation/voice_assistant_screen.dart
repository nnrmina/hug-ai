import 'package:flutter/material.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/permissions/permission_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/models/assistant_response_model.dart';
import '../../../shared/widgets/confirmation_panel.dart';
import '../../home/widgets/big_microphone_button.dart';
import '../data/speech_engine_service.dart';
import 'assistant_flow.dart';

/// Type or dictate a command (fallback when hands-free mode is not enough).
class VoiceAssistantScreen extends StatefulWidget {
  final AssistantFlow? flow;

  const VoiceAssistantScreen({super.key, this.flow});

  @override
  State<VoiceAssistantScreen> createState() => _VoiceAssistantScreenState();
}

class _VoiceAssistantScreenState extends State<VoiceAssistantScreen> {
  final SpeechEngineService _speech = SpeechEngineService();
  late final AssistantFlow _flow = widget.flow ?? AssistantFlow();
  final TextEditingController _textController = TextEditingController();

  bool _isListening = false;
  bool _isLoading = false;
  String _assistantReply = 'Əmrinizi yazın və ya mikrofona toxunub danışın.';
  AssistantResponseModel? _pending;

  @override
  void initState() {
    super.initState();
    _speech.onListeningChanged = (value) {
      if (mounted) setState(() => _isListening = value);
    };
    _speech.onError = (message) {
      if (mounted) setState(() => _assistantReply = message);
    };
  }

  @override
  void dispose() {
    _speech.dispose();
    _textController.dispose();
    super.dispose();
  }

  Future<void> _sendCommand(String commandText) async {
    final text = commandText.trim();
    if (text.isEmpty || _isLoading) return;
    FocusScope.of(context).unfocus();
    await _speech.stopListening();
    if (!mounted) return;
    setState(() {
      _isLoading = true;
      _pending = null;
    });

    final AssistantResponseModel result;
    try {
      result = await _flow.repository.sendCommand(text);
    } on AppException catch (e) {
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _assistantReply = e.message;
      });
      return;
    }
    if (!mounted) return;

    if (AssistantFlow.isCallConfirmation(result)) {
      setState(() => _assistantReply = result.response);
      final flowResult = await _flow.runCallFlow(context, result, text);
      if (!mounted) return;
      setState(() {
        _isLoading = false;
        _assistantReply = flowResult.message;
      });
      if (!flowResult.dialerOpened) await _speech.speak(flowResult.message);
      return;
    }

    setState(() {
      _isLoading = false;
      _assistantReply = result.response.isNotEmpty
          ? result.response
          : 'Bağışlayın, başa düşmədim.';
      _pending =
          result.needsConfirmation && result.actionId != null ? result : null;
    });
    await _speech.speak(_assistantReply);
  }

  Future<void> _confirmAction() async {
    final pending = _pending;
    if (pending?.actionId == null || _isLoading) return;
    setState(() => _isLoading = true);
    String message;
    var keepPending = false;
    try {
      final r = await _flow.repository.confirmAction(pending!.actionId!);
      message = r.response.isNotEmpty ? r.response : 'Təsdiqləndi.';
    } on AppException catch (e) {
      message = e.message;
      keepPending = e.statusCode == null;
    }
    if (!mounted) return;
    setState(() {
      _isLoading = false;
      if (!keepPending) _pending = null;
      _assistantReply = message;
    });
    await _speech.speak(message);
  }

  Future<void> _cancelAction() async {
    final pending = _pending;
    if (pending == null || _isLoading) return;
    setState(() => _isLoading = true);
    await _flow.cancelQuietly(pending.actionId);
    if (!mounted) return;
    setState(() {
      _isLoading = false;
      _pending = null;
      _assistantReply = 'Əməliyyat ləğv edildi.';
    });
  }

  Future<void> _toggleListening() async {
    if (_isLoading) return;
    if (_speech.isListening) {
      await _speech.stopListening();
      return;
    }
    final outcome = await _flow.permissions.requestMicrophone();
    if (!mounted) return;
    if (outcome != PermissionOutcome.granted) {
      setState(() => _assistantReply =
          'Mikrofon icazəsi verilmədi. Əmrinizi yaza bilərsiniz.');
      return;
    }
    final ok = await _speech.startListening(
      onResult: (words, isFinal) {
        if (!mounted) return;
        setState(() => _textController.text = words);
        if (isFinal && words.trim().isNotEmpty) _sendCommand(words);
      },
    );
    if (!mounted) return;
    if (!ok) {
      setState(() => _assistantReply =
          'Nitq tanıma əlçatan deyil. Əmrinizi yazın.');
    } else if (_speech.localeNote != null) {
      setState(() => _assistantReply = _speech.localeNote!);
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Yazaraq əmr ver')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(20.0),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                children: [
                  Expanded(
                    child: TextField(
                      controller: _textController,
                      style: const TextStyle(fontSize: 20),
                      textInputAction: TextInputAction.send,
                      decoration: InputDecoration(
                        labelText: 'Əmriniz',
                        labelStyle: const TextStyle(fontSize: 18),
                        hintText: 'Məsələn: Qızıma zəng et',
                        hintStyle: const TextStyle(fontSize: 18),
                        border: OutlineInputBorder(
                          borderRadius: BorderRadius.circular(14),
                        ),
                      ),
                      onSubmitted: _sendCommand,
                    ),
                  ),
                  const SizedBox(width: 8),
                  Semantics(
                    button: true,
                    label: 'Göndər',
                    excludeSemantics: true,
                    child: ElevatedButton(
                      style: ElevatedButton.styleFrom(
                        backgroundColor: AppTheme.primaryGreen,
                        foregroundColor: Colors.white,
                        minimumSize: const Size(64, 64),
                      ),
                      onPressed: _isLoading
                          ? null
                          : () => _sendCommand(_textController.text),
                      child: const Icon(Icons.send_rounded, size: 28),
                    ),
                  ),
                ],
              ),
              const SizedBox(height: 20),
              Card(
                elevation: 2,
                child: Padding(
                  padding: const EdgeInsets.all(20.0),
                  child: Column(
                    crossAxisAlignment: CrossAxisAlignment.start,
                    children: [
                      const Text(
                        'YAXIN AI cavabı:',
                        style: TextStyle(
                            fontSize: 18, color: AppTheme.textSecondary),
                      ),
                      const SizedBox(height: 8),
                      if (_isLoading)
                        const Center(child: CircularProgressIndicator())
                      else
                        Semantics(
                          liveRegion: true,
                          child: Text(
                            _assistantReply,
                            style: const TextStyle(
                              fontSize: 20,
                              color: AppTheme.textPrimary,
                            ),
                          ),
                        ),
                    ],
                  ),
                ),
              ),
              const SizedBox(height: 20),
              if (_pending != null)
                ConfirmationPanel(
                  message: 'Təsdiq edirsiniz?',
                  busy: _isLoading,
                  onConfirm: _confirmAction,
                  onCancel: _cancelAction,
                )
              else
                Center(
                  child: BigMicrophoneButton(
                    isListening: _isListening,
                    onTap: _toggleListening,
                  ),
                ),
            ],
          ),
        ),
      ),
    );
  }
}
