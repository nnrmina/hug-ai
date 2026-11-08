import 'package:flutter/material.dart';

import '../../../app/routes.dart';
import '../../../core/auth/device_auth_service.dart';
import '../../../core/constants/app_strings.dart';
import '../../../core/errors/app_exception.dart';
import '../../../core/permissions/permission_service.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/models/assistant_response_model.dart';
import '../../../shared/widgets/confirmation_panel.dart';
import '../../voice/data/speech_engine_service.dart';
import '../../voice/presentation/assistant_flow.dart';
import '../widgets/big_microphone_button.dart';

class HomeScreen extends StatefulWidget {
  final AssistantFlow? flow;
  final bool autoStartListening;

  const HomeScreen({super.key, this.flow, this.autoStartListening = true});

  @override
  State<HomeScreen> createState() => _HomeScreenState();
}

class _HomeScreenState extends State<HomeScreen> with WidgetsBindingObserver {
  final SpeechEngineService _speech = SpeechEngineService();
  late final AssistantFlow _flow = widget.flow ?? AssistantFlow();
  PermissionService get _permissions => _flow.permissions;

  bool _isListening = false;
  bool _busy = false;
  bool _starting = false;
  bool _wasPaused = false;
  String _transcript = '';
  String _status = AppStrings.micTapPrompt;
  String? _localeNote;
  AssistantResponseModel? _pending;

  @override
  void initState() {
    super.initState();
    WidgetsBinding.instance.addObserver(this);
    _speech.onListeningChanged = (value) {
      if (mounted) setState(() => _isListening = value);
    };
    _speech.onError = (message) {
      if (mounted && !_busy) setState(() => _status = message);
    };
    if (widget.autoStartListening) {
      WidgetsBinding.instance.addPostFrameCallback((_) => _initMicAndListen());
    }
  }

  @override
  void dispose() {
    WidgetsBinding.instance.removeObserver(this);
    _speech.dispose();
    super.dispose();
  }

  @override
  void didChangeAppLifecycleState(AppLifecycleState state) {
    if (state == AppLifecycleState.paused) {
      _wasPaused = true;
      _speech.stopListening();
    } else if (state == AppLifecycleState.resumed && _wasPaused) {
      _wasPaused = false;
      // E.g. back from the phone dialer: listen again.
      _startListening();
    }
  }

  bool get _isCurrentRoute => ModalRoute.of(context)?.isCurrent ?? true;

  Future<void> _initMicAndListen() async {
    final outcome = await _permissions.requestMicrophone();
    if (!mounted) return;
    if (outcome != PermissionOutcome.granted) {
      setState(() => _status = AppStrings.micPermissionDenied);
      return;
    }
    await _startListening();
  }

  Future<void> _startListening() async {
    if (!mounted ||
        _starting ||
        _busy ||
        _pending != null ||
        _speech.isListening ||
        !_isCurrentRoute) {
      return;
    }
    _starting = true;
    setState(() {
      _transcript = '';
      _status = AppStrings.micListening;
    });
    final ok = await _speech.startListening(onResult: _onSpeechResult);
    _starting = false;
    if (!mounted) return;
    setState(() {
      _localeNote = _speech.localeNote;
      if (!ok) {
        _status =
            'Nitq tanıma bu telefonda əlçatan deyil. "Yazaraq əmr ver" düyməsindən istifadə edin.';
      }
    });
  }

  Future<void> _toggleMic() async {
    if (_busy || _pending != null) return;
    if (_speech.isListening) {
      await _speech.stopListening();
      if (mounted) setState(() => _status = AppStrings.micTapPrompt);
      return;
    }
    final outcome = await _permissions.requestMicrophone();
    if (!mounted) return;
    if (outcome != PermissionOutcome.granted) {
      setState(() => _status = AppStrings.micPermissionDenied);
      if (outcome == PermissionOutcome.permanentlyDenied) {
        await _permissions.openSettings();
      }
      return;
    }
    await _startListening();
  }

  void _onSpeechResult(String text, bool isFinal) {
    if (!mounted || _busy) return;
    setState(() => _transcript = text);
    // Act ONLY on the final result — never on a partial transcript.
    if (isFinal && text.trim().isNotEmpty) {
      _handleCommand(text.trim());
    }
  }

  Future<void> _speakThenListen(String message) async {
    await _speech.speak(message);
    if (mounted) await _startListening();
  }

  Future<void> _handleCommand(String text) async {
    if (_busy) return;
    _busy = true;
    await _speech.stopListening();
    if (!mounted) return;
    setState(() => _status = 'Əmriniz yoxlanılır...');

    final AssistantResponseModel res;
    try {
      res = await _flow.repository.sendCommand(text);
    } on AppException catch (e) {
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = e.message;
      });
      await _speech.speak(e.message);
      return;
    }
    if (!mounted) return;

    if (AssistantFlow.isCallConfirmation(res)) {
      setState(() => _status = res.response);
      final result = await _flow.runCallFlow(context, res, text);
      if (!mounted) return;
      setState(() {
        _busy = false;
        _status = result.message;
      });
      if (!result.dialerOpened) await _speakThenListen(result.message);
      // If the dialer opened, listening resumes when the app is resumed.
      return;
    }

    if (res.needsConfirmation && res.actionId != null) {
      setState(() {
        _busy = false;
        _pending = res;
        _status = res.response;
      });
      await _speech.speak(
          '${res.response} Təsdiq üçün ekrandakı Bəli düyməsinə toxunun.');
      return;
    }

    final message = res.response.isNotEmpty
        ? res.response
        : 'Bağışlayın, başa düşmədim. Yenidən deyin.';
    setState(() {
      _busy = false;
      _status = message;
    });
    await _speakThenListen(message);
  }

  Future<void> _confirmPending() async {
    final pending = _pending;
    if (pending?.actionId == null || _busy) return;
    setState(() => _busy = true);
    String message;
    var keepPending = false;
    try {
      final r = await _flow.repository.confirmAction(pending!.actionId!);
      message = r.response.isNotEmpty ? r.response : 'Təsdiqləndi.';
    } on AppException catch (e) {
      message = e.message;
      keepPending = e.statusCode == null; // network error: allow retry
    }
    if (!mounted) return;
    setState(() {
      _busy = false;
      if (!keepPending) _pending = null;
      _status = message;
    });
    if (keepPending) {
      await _speech.speak(message);
    } else {
      await _speakThenListen(message);
    }
  }

  Future<void> _cancelPending() async {
    final pending = _pending;
    if (pending == null || _busy) return;
    setState(() => _busy = true);
    await _flow.cancelQuietly(pending.actionId);
    if (!mounted) return;
    setState(() {
      _busy = false;
      _pending = null;
      _status = 'Ləğv edildi.';
    });
    await _speakThenListen('Ləğv edildi.');
  }

  Future<void> _open(String route) async {
    await _speech.stopListening();
    await _speech.stopSpeaking();
    if (!mounted) return;
    await Navigator.pushNamed(context, route);
    if (mounted) await _startListening();
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.symmetric(horizontal: 20, vertical: 14),
          child: Column(
            crossAxisAlignment: CrossAxisAlignment.stretch,
            children: [
              Row(
                mainAxisAlignment: MainAxisAlignment.spaceBetween,
                children: [
                  _CircleTopButton(
                    icon: Icons.keyboard_rounded,
                    semanticsLabel: 'Yazaraq əmr ver',
                    onTap: () => _open(AppRoutes.voiceAssistant),
                  ),
                  Container(
                    padding:
                        const EdgeInsets.symmetric(horizontal: 20, vertical: 12),
                    decoration: BoxDecoration(
                      color: Colors.white.withValues(alpha: 0.85),
                      borderRadius: BorderRadius.circular(26),
                    ),
                    child: const Row(
                      mainAxisSize: MainAxisSize.min,
                      children: [
                        Icon(Icons.auto_awesome,
                            size: 20, color: AppTheme.textPrimary),
                        SizedBox(width: 6),
                        Text(
                          'Yaxın AI',
                          style: TextStyle(
                            fontSize: 18,
                            fontWeight: FontWeight.w700,
                            color: AppTheme.textPrimary,
                          ),
                        ),
                      ],
                    ),
                  ),
                  _CircleTopButton(
                    icon: Icons.settings_rounded,
                    semanticsLabel: 'Tənzimləmələr',
                    onTap: () => _open(AppRoutes.settings),
                  ),
                ],
              ),
              ValueListenableBuilder<String?>(
                valueListenable: DeviceAuthService.accountNotice,
                builder: (context, notice, _) => notice == null
                    ? const SizedBox.shrink()
                    : Padding(
                        padding: const EdgeInsets.only(top: 16),
                        child: Semantics(
                          liveRegion: true,
                          child: Container(
                            padding: const EdgeInsets.fromLTRB(16, 8, 4, 8),
                            decoration: BoxDecoration(
                              color: Colors.white,
                              borderRadius: BorderRadius.circular(16),
                              border: Border.all(color: AppTheme.warningAmber),
                            ),
                            child: Row(
                              children: [
                                Expanded(
                                  child: Text(
                                    notice,
                                    style: const TextStyle(
                                      fontSize: 16,
                                      fontWeight: FontWeight.w600,
                                      color: AppTheme.warningAmber,
                                    ),
                                  ),
                                ),
                                IconButton(
                                  iconSize: 28,
                                  tooltip: 'Bağla',
                                  icon: const Icon(Icons.close_rounded),
                                  onPressed: () =>
                                      DeviceAuthService.accountNotice.value =
                                          null,
                                ),
                              ],
                            ),
                          ),
                        ),
                      ),
              ),
              const SizedBox(height: 28),
              RichText(
                textAlign: TextAlign.center,
                text: const TextSpan(
                  style: TextStyle(
                    fontSize: 28,
                    fontWeight: FontWeight.w600,
                    height: 1.28,
                    color: AppTheme.textPrimary,
                  ),
                  children: [
                    TextSpan(text: 'Bu gün sizə necə '),
                    TextSpan(
                      text: 'kömək\n',
                      style: TextStyle(
                        color: AppTheme.textAccentGreen,
                        fontWeight: FontWeight.w800,
                      ),
                    ),
                    TextSpan(text: 'edə bilərəm?'),
                  ],
                ),
              ),
              const SizedBox(height: 16),
              if (_transcript.isNotEmpty)
                Text(
                  '"$_transcript"',
                  style: const TextStyle(
                    fontSize: 20,
                    fontStyle: FontStyle.italic,
                    color: AppTheme.textPrimary,
                  ),
                  textAlign: TextAlign.center,
                ),
              const SizedBox(height: 8),
              Semantics(
                liveRegion: true,
                child: Text(
                  _status,
                  style: Theme.of(context).textTheme.bodyLarge,
                  textAlign: TextAlign.center,
                ),
              ),
              if (_localeNote != null) ...[
                const SizedBox(height: 8),
                Text(
                  _localeNote!,
                  style: const TextStyle(
                    fontSize: 16,
                    color: AppTheme.warningAmber,
                    fontWeight: FontWeight.w600,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
              const SizedBox(height: 24),
              if (_pending != null)
                ConfirmationPanel(
                  message: _pending!.response,
                  busy: _busy,
                  onConfirm: _confirmPending,
                  onCancel: _cancelPending,
                )
              else
                Center(
                  child: _busy
                      ? const SizedBox(
                          height: 176,
                          child: Center(
                            child: SizedBox(
                              width: 64,
                              height: 64,
                              child: CircularProgressIndicator(strokeWidth: 6),
                            ),
                          ),
                        )
                      : BigMicrophoneButton(
                          isListening: _isListening,
                          onTap: _toggleMic,
                        ),
                ),
              const SizedBox(height: 24),
              Row(
                children: [
                  Expanded(
                    child: _FeatureButton(
                      icon: Icons.alarm_rounded,
                      label: 'Xatırlatmalar',
                      onTap: () => _open(AppRoutes.reminders),
                    ),
                  ),
                  const SizedBox(width: 12),
                  Expanded(
                    child: _FeatureButton(
                      icon: Icons.shield_rounded,
                      label: 'Rəqəmsal Qalxan',
                      onTap: () => _open(AppRoutes.digitalShield),
                    ),
                  ),
                ],
              ),
            ],
          ),
        ),
      ),
    );
  }
}

class _CircleTopButton extends StatelessWidget {
  final IconData icon;
  final String semanticsLabel;
  final VoidCallback onTap;

  const _CircleTopButton({
    required this.icon,
    required this.semanticsLabel,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: semanticsLabel,
      excludeSemantics: true,
      child: Tooltip(
        message: semanticsLabel,
        child: Material(
          color: Colors.white.withValues(alpha: 0.9),
          shape: const CircleBorder(),
          child: InkWell(
            customBorder: const CircleBorder(),
            onTap: onTap,
            child: SizedBox(
              width: 56,
              height: 56,
              child: Icon(icon, size: 28, color: AppTheme.textPrimary),
            ),
          ),
        ),
      ),
    );
  }
}

class _FeatureButton extends StatelessWidget {
  final IconData icon;
  final String label;
  final VoidCallback onTap;

  const _FeatureButton({
    required this.icon,
    required this.label,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Semantics(
      button: true,
      label: label,
      excludeSemantics: true,
      child: Material(
        color: AppTheme.primaryGreen,
        borderRadius: BorderRadius.circular(18),
        child: InkWell(
          borderRadius: BorderRadius.circular(18),
          onTap: onTap,
          child: ConstrainedBox(
            constraints: const BoxConstraints(minHeight: 88),
            child: Padding(
              padding: const EdgeInsets.all(12),
              child: Column(
                mainAxisAlignment: MainAxisAlignment.center,
                children: [
                  Icon(icon, size: 32, color: Colors.white),
                  const SizedBox(height: 6),
                  Text(
                    label,
                    textAlign: TextAlign.center,
                    style: const TextStyle(
                      fontSize: 18,
                      fontWeight: FontWeight.w700,
                      color: Colors.white,
                    ),
                  ),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
