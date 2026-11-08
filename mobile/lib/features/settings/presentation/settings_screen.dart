import 'package:flutter/material.dart';
import 'package:shared_preferences/shared_preferences.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';

class SettingsScreen extends StatefulWidget {
  final ApiClient? apiClient;

  const SettingsScreen({super.key, this.apiClient});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  static const _kVoiceResponse = 'pref_voice_response';
  static const _kVoiceSpeed = 'pref_voice_speed';
  static const _kTheme = 'pref_theme';

  late final ApiClient _apiClient = widget.apiClient ?? ApiClient();
  bool _voiceResponse = true;
  double _voiceSpeed = 1.0;
  String _theme = 'light';
  String _statusMessage = '';
  bool _statusIsError = false;
  bool _saving = false;

  @override
  void initState() {
    super.initState();
    _loadLocal();
  }

  Future<void> _loadLocal() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      if (!mounted) return;
      setState(() {
        _voiceResponse = prefs.getBool(_kVoiceResponse) ?? _voiceResponse;
        _voiceSpeed =
            (prefs.getDouble(_kVoiceSpeed) ?? _voiceSpeed).clamp(0.5, 2.0);
        final theme = prefs.getString(_kTheme);
        if (theme == 'light' || theme == 'dark' || theme == 'high_contrast') {
          _theme = theme!;
        }
      });
    } catch (_) {
      // Keep defaults.
    }
  }

  Future<bool> _saveLocal() async {
    try {
      final prefs = await SharedPreferences.getInstance();
      await prefs.setBool(_kVoiceResponse, _voiceResponse);
      await prefs.setDouble(_kVoiceSpeed, _voiceSpeed);
      await prefs.setString(_kTheme, _theme);
      return true;
    } catch (_) {
      return false;
    }
  }

  Future<void> _savePreferences() async {
    if (_saving) return;
    setState(() {
      _saving = true;
      _statusMessage = '';
    });
    final savedLocally = await _saveLocal();
    String message;
    bool isError;
    try {
      await _apiClient.patchJson(
        '/users/preferences',
        {
          'voice_response': _voiceResponse,
          'voice_speed': double.parse(_voiceSpeed.toStringAsFixed(1)),
          'theme': _theme,
        },
      );
      message = 'Seçimlər uğurla yadda saxlanıldı.';
      isError = false;
    } on AppException catch (e) {
      message = savedLocally
          ? 'Serverə göndərilmədi: ${e.message}\nSeçimlər yalnız bu telefonda yadda saxlanıldı.'
          : 'Seçimləri yadda saxlamaq mümkün olmadı: ${e.message}';
      isError = true;
    } catch (_) {
      message = savedLocally
          ? 'Serverə göndərilmədi. Seçimlər yalnız bu telefonda yadda saxlanıldı.'
          : 'Seçimləri yadda saxlamaq mümkün olmadı.';
      isError = true;
    }
    if (!mounted) return;
    setState(() {
      _saving = false;
      _statusMessage = message;
      _statusIsError = isError;
    });
  }

  @override
  Widget build(BuildContext context) {
    const titleStyle = TextStyle(
        fontSize: 20, fontWeight: FontWeight.w600, color: AppTheme.textPrimary);
    const bodyStyle = TextStyle(fontSize: 16, color: AppTheme.textSecondary);
    return Scaffold(
      appBar: AppBar(title: const Text('Tənzimləmələr və Məxfilik')),
      body: SafeArea(
        child: ListView(
          padding: const EdgeInsets.all(24.0),
          children: [
            Card(
              child: Padding(
                padding: const EdgeInsets.all(16.0),
                child: Column(
                  children: [
                    SwitchListTile(
                      title: const Text('Səsli Cavab', style: titleStyle),
                      subtitle: const Text('YAXIN AI cavabları səsləndirsin',
                          style: bodyStyle),
                      value: _voiceResponse,
                      onChanged: (val) => setState(() => _voiceResponse = val),
                    ),
                    const Divider(),
                    ListTile(
                      title: Text(
                        'Danışıq Sürəti: ${_voiceSpeed.toStringAsFixed(1)}x',
                        style: titleStyle,
                      ),
                      subtitle: Slider(
                        value: _voiceSpeed,
                        min: 0.5,
                        max: 2.0,
                        divisions: 15,
                        label: '${_voiceSpeed.toStringAsFixed(1)}x',
                        semanticFormatterCallback: (v) =>
                            'Danışıq sürəti ${v.toStringAsFixed(1)}',
                        onChanged: (val) => setState(() => _voiceSpeed = val),
                      ),
                    ),
                    const Divider(),
                    ListTile(
                      title: const Text('Görünüş', style: titleStyle),
                      trailing: DropdownButton<String>(
                        value: _theme,
                        style: const TextStyle(
                            fontSize: 18, color: AppTheme.textPrimary),
                        items: const [
                          DropdownMenuItem(
                              value: 'light', child: Text('İşıqlı')),
                          DropdownMenuItem(
                              value: 'dark', child: Text('Qaranlıq')),
                          DropdownMenuItem(
                              value: 'high_contrast',
                              child: Text('Yüksək Kontrast')),
                        ],
                        onChanged: (val) {
                          if (val != null) setState(() => _theme = val);
                        },
                      ),
                    ),
                  ],
                ),
              ),
            ),
            const SizedBox(height: 16),
            AccessibleActionButton(
              label: _saving ? 'Yadda saxlanılır...' : 'Seçimləri Yadda Saxla',
              icon: Icons.save_rounded,
              backgroundColor: AppTheme.primaryGreen,
              onPressed: _saving ? null : _savePreferences,
            ),
            if (_statusMessage.isNotEmpty) ...[
              const SizedBox(height: 12),
              Semantics(
                liveRegion: true,
                child: Text(
                  _statusMessage,
                  style: TextStyle(
                    fontSize: 18,
                    fontWeight: FontWeight.w600,
                    color: _statusIsError
                        ? AppTheme.dangerRed
                        : AppTheme.textAccentGreen,
                  ),
                  textAlign: TextAlign.center,
                ),
              ),
            ],
            const SizedBox(height: 24),
            const Card(
              child: Padding(
                padding: EdgeInsets.all(18.0),
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Text(
                      'Məxfilik və Təhlükəsizlik',
                      style: TextStyle(
                          fontSize: 20,
                          fontWeight: FontWeight.bold,
                          color: AppTheme.textPrimary),
                    ),
                    SizedBox(height: 10),
                    Text('• Kontaktlar yalnız telefonda axtarılır, serverə göndərilmir.',
                        style: bodyStyle),
                    Text('• SMS, WhatsApp, şəkillər və GPS oxunmur.',
                        style: bodyStyle),
                    Text('• Hər zəngdən əvvəl sizin təsdiqiniz tələb olunur.',
                        style: bodyStyle),
                    Text('• Bank və ödəniş əməliyyatları edilmir.',
                        style: bodyStyle),
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
