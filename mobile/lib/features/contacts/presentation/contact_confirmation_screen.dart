import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';

import '../../../core/constants/app_strings.dart';
import '../../../core/errors/app_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';
import '../../voice/data/speech_engine_service.dart';
import '../../voice/data/voice_assistant_repository.dart';
import '../domain/local_contact_alias.dart';

/// Arguments for [ContactConfirmationScreen]. Always pass real matches.
class ContactConfirmationArgs {
  final List<LocalContactAlias> candidates;
  final String? actionId;

  const ContactConfirmationArgs({required this.candidates, this.actionId});
}

/// Returned via Navigator.pop.
class CallOutcome {
  final bool dialed;

  /// True when the server-side action is no longer pending (confirmed,
  /// expired or rejected), so the caller must not cancel it.
  final bool actionResolved;
  final String message;

  const CallOutcome({
    required this.dialed,
    required this.actionResolved,
    required this.message,
  });
}

class ContactConfirmationScreen extends StatefulWidget {
  final ContactConfirmationArgs? args;
  final VoiceAssistantRepository? repository;

  /// Injected for tests; defaults to opening the system dialer.
  final Future<bool> Function(Uri uri)? dialer;

  const ContactConfirmationScreen({
    super.key,
    this.args,
    this.repository,
    this.dialer,
  });

  @override
  State<ContactConfirmationScreen> createState() =>
      _ContactConfirmationScreenState();
}

class _ContactConfirmationScreenState extends State<ContactConfirmationScreen> {
  final SpeechEngineService _speech = SpeechEngineService();
  late final VoiceAssistantRepository _repository =
      widget.repository ?? VoiceAssistantRepository();

  ContactConfirmationArgs? _args;
  LocalContactAlias? _selected;
  bool _busy = false;
  bool _actionResolved = false;
  String? _error;
  bool _initialized = false;

  @override
  void didChangeDependencies() {
    super.didChangeDependencies();
    if (_initialized) return;
    _initialized = true;
    final routeArg = ModalRoute.of(context)?.settings.arguments;
    _args = widget.args ??
        (routeArg is ContactConfirmationArgs ? routeArg : null);
    final candidates = _args?.candidates ?? const [];
    if (candidates.length == 1) {
      _selected = candidates.first;
      _announce(candidates.first);
    } else if (candidates.length > 1) {
      _speech.speak(
          'Bu adda bir neçə kontakt var. Hansına zəng edək? Ekranda seçin.');
    }
  }

  @override
  void dispose() {
    _speech.dispose();
    super.dispose();
  }

  void _select(LocalContactAlias contact) {
    setState(() {
      _selected = contact;
      _error = null;
    });
    _announce(contact);
  }

  void _announce(LocalContactAlias contact) {
    _speech.speak('${contact.displayName}. Zəng edilsin? Bəli və ya Xeyr '
        'düyməsinə toxunun.');
  }

  String _sanitize(String phone) => phone.replaceAll(RegExp(r'[^0-9+]'), '');

  Future<bool> _openDialer(Uri uri) async {
    if (widget.dialer != null) return widget.dialer!(uri);
    try {
      return await launchUrl(uri, mode: LaunchMode.externalApplication);
    } catch (_) {
      return false;
    }
  }

  Future<void> _confirm() async {
    final contact = _selected;
    if (contact == null || _busy) return;
    setState(() {
      _busy = true;
      _error = null;
    });
    await _speech.stopSpeaking();

    final actionId = _args?.actionId;
    if (actionId != null && !_actionResolved) {
      try {
        await _repository.confirmAction(actionId);
        _actionResolved = true;
      } on AppException catch (e) {
        if (!mounted) return;
        setState(() {
          _busy = false;
          _error = e.message;
          // 404/409: no longer pending on the server — do not dial.
          _actionResolved = e.statusCode == 404 || e.statusCode == 409;
        });
        _speech.speak(e.message);
        return;
      }
    }

    final number = _sanitize(contact.phoneNumber);
    final opened =
        number.isNotEmpty && await _openDialer(Uri(scheme: 'tel', path: number));
    if (!mounted) return;
    if (opened) {
      Navigator.of(context).pop(CallOutcome(
        dialed: true,
        actionResolved: true,
        message: '${contact.displayName} — nömrə yığıcı açıldı.',
      ));
      return;
    }
    final msg =
        'Nömrə yığıcı açıla bilmədi. Zəng edilmədi. Nömrə: ${contact.phoneNumber}';
    setState(() {
      _busy = false;
      _error = msg;
      _actionResolved = true;
    });
    _speech.speak('Nömrə yığıcı açıla bilmədi. Zəng edilmədi.');
  }

  void _cancel() {
    Navigator.of(context).pop(CallOutcome(
      dialed: false,
      actionResolved: _actionResolved,
      message: _error ?? 'Zəng ləğv edildi.',
    ));
  }

  @override
  Widget build(BuildContext context) {
    final candidates = _args?.candidates ?? const <LocalContactAlias>[];
    return Scaffold(
      appBar: AppBar(title: const Text('Zəngi təsdiqləyin')),
      body: SafeArea(
        child: SingleChildScrollView(
          padding: const EdgeInsets.all(24.0),
          child: candidates.isEmpty
              ? _buildNoContact()
              : (_selected == null
                  ? _buildChooser(candidates)
                  : _buildConfirm(_selected!)),
        ),
      ),
    );
  }

  Widget _buildNoContact() {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        const Icon(Icons.person_off_rounded,
            size: 72, color: AppTheme.dangerRed),
        const SizedBox(height: 16),
        Text(
          '${AppStrings.contactNotFound}. Zəng edilmədi.',
          style: Theme.of(context).textTheme.headlineMedium,
          textAlign: TextAlign.center,
        ),
        const SizedBox(height: 32),
        AccessibleActionButton(
          label: AppStrings.backButton,
          icon: Icons.arrow_back_rounded,
          backgroundColor: AppTheme.primaryGreen,
          onPressed: _cancel,
        ),
      ],
    );
  }

  Widget _buildChooser(List<LocalContactAlias> candidates) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Text(
          'Bu adda bir neçə kontakt var. Hansına zəng edək?',
          style: Theme.of(context).textTheme.headlineMedium,
        ),
        const SizedBox(height: 20),
        for (final c in candidates) ...[
          Semantics(
            button: true,
            label: '${c.displayName}, nömrə ${c.phoneNumber}. Seçmək üçün toxunun',
            excludeSemantics: true,
            child: Card(
              elevation: 2,
              child: InkWell(
                borderRadius: BorderRadius.circular(12),
                onTap: () => _select(c),
                child: ConstrainedBox(
                  constraints: const BoxConstraints(minHeight: 80),
                  child: Padding(
                    padding: const EdgeInsets.all(16),
                    child: Row(
                      children: [
                        const Icon(Icons.person_rounded,
                            size: 40, color: AppTheme.textAccentGreen),
                        const SizedBox(width: 16),
                        Expanded(
                          child: Column(
                            crossAxisAlignment: CrossAxisAlignment.start,
                            children: [
                              Text(c.displayName,
                                  style: Theme.of(context).textTheme.titleLarge),
                              Text(c.phoneNumber,
                                  style: Theme.of(context).textTheme.bodyLarge),
                            ],
                          ),
                        ),
                      ],
                    ),
                  ),
                ),
              ),
            ),
          ),
          const SizedBox(height: 12),
        ],
        const SizedBox(height: 12),
        AccessibleActionButton(
          label: AppStrings.rejectButton,
          icon: Icons.close_rounded,
          backgroundColor: AppTheme.dangerRed,
          semanticsLabel: 'Xeyr, zəng etmə',
          onPressed: _cancel,
        ),
      ],
    );
  }

  Widget _buildConfirm(LocalContactAlias contact) {
    final resolvedWithError = _actionResolved && _error != null;
    return Column(
      crossAxisAlignment: CrossAxisAlignment.stretch,
      children: [
        Card(
          elevation: 4,
          shape: RoundedRectangleBorder(
            borderRadius: BorderRadius.circular(24),
          ),
          child: Padding(
            padding: const EdgeInsets.all(24.0),
            child: Column(
              children: [
                const CircleAvatar(
                  radius: 44,
                  backgroundColor: AppTheme.primaryGreen,
                  child: Icon(Icons.phone_rounded, size: 48, color: Colors.white),
                ),
                const SizedBox(height: 16),
                Text(
                  contact.displayName,
                  style: Theme.of(context).textTheme.headlineMedium,
                  textAlign: TextAlign.center,
                ),
                const SizedBox(height: 8),
                Text(
                  contact.phoneNumber,
                  style: Theme.of(context).textTheme.titleLarge,
                ),
                const SizedBox(height: 16),
                const Text(
                  'Bu nömrəyə zəng edilsin?',
                  style: TextStyle(
                    fontSize: 22,
                    fontWeight: FontWeight.w700,
                    color: AppTheme.textPrimary,
                  ),
                  textAlign: TextAlign.center,
                ),
              ],
            ),
          ),
        ),
        if (_error != null) ...[
          const SizedBox(height: 16),
          Semantics(
            liveRegion: true,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: BoxDecoration(
                color: AppTheme.dangerRed.withValues(alpha: 0.08),
                borderRadius: BorderRadius.circular(16),
                border: Border.all(color: AppTheme.dangerRed),
              ),
              child: Text(
                _error!,
                style: const TextStyle(
                  fontSize: 18,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.dangerRed,
                ),
              ),
            ),
          ),
        ],
        const SizedBox(height: 24),
        if (_busy)
          const Center(
            child: Padding(
              padding: EdgeInsets.all(16),
              child: CircularProgressIndicator(),
            ),
          )
        else if (resolvedWithError)
          AccessibleActionButton(
            label: AppStrings.backButton,
            icon: Icons.arrow_back_rounded,
            backgroundColor: AppTheme.primaryGreen,
            onPressed: _cancel,
          )
        else ...[
          AccessibleActionButton(
            label: AppStrings.confirmCallButton,
            icon: Icons.call_rounded,
            backgroundColor: AppTheme.confirmGreen,
            semanticsLabel: 'Bəli, ${contact.displayName} nömrəsinə zəng et',
            onPressed: _confirm,
          ),
          const SizedBox(height: 16),
          AccessibleActionButton(
            label: AppStrings.rejectButton,
            icon: Icons.call_end_rounded,
            backgroundColor: AppTheme.dangerRed,
            semanticsLabel: 'Xeyr, zəng etmə',
            onPressed: _cancel,
          ),
        ],
      ],
    );
  }
}
