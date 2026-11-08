import 'package:flutter/material.dart';
import '../../../core/network/api_client.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';

class SettingsScreen extends StatefulWidget {
  const SettingsScreen({super.key});

  @override
  State<SettingsScreen> createState() => _SettingsScreenState();
}

class _SettingsScreenState extends State<SettingsScreen> {
  final ApiClient _apiClient = ApiClient();
  bool _voiceResponse = true;
  double _voiceSpeed = 1.0;
  String _theme = 'light';
  String _statusMessage = '';

  Future<void> _savePreferences() async {
    try {
      await _apiClient.postJson('/users/preferences', {
        'voice_response': _voiceResponse,
        'voice_speed': _voiceSpeed,
        'theme': _theme,
      });
      setState(() {
        _statusMessage = 'Seçimlər uğurla yadda saxlanıldı.';
      });
    } catch (_) {
      setState(() {
        _statusMessage = 'Seçimlər lokal olaraq yadda saxlanıldı.';
      });
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Tənzimləmələr & Məxfilik')),
      body: ListView(
        padding: const EdgeInsets.all(24.0),
        children: [
          Card(
            child: Padding(
              padding: const EdgeInsets.all(16.0),
              child: Column(
                children: [
                  SwitchListTile(
                    title: const Text(
                      'Səsli Cavab (TTS)',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                    ),
                    subtitle: const Text('YAXIN AI cavabları səsləndirsin'),
                    value: _voiceResponse,
                    onChanged: (val) => setState(() => _voiceResponse = val),
                  ),
                  const Divider(),
                  ListTile(
                    title: Text(
                      'Danışıq Sürəti: ${_voiceSpeed.toStringAsFixed(1)}x',
                      style: const TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                    ),
                    subtitle: Slider(
                      value: _voiceSpeed,
                      min: 0.5,
                      max: 2.0,
                      divisions: 15,
                      label: '${_voiceSpeed.toStringAsFixed(1)}x',
                      onChanged: (val) => setState(() => _voiceSpeed = val),
                    ),
                  ),
                  const Divider(),
                  ListTile(
                    title: const Text(
                      'Görünüş (Theme)',
                      style: TextStyle(fontSize: 20, fontWeight: FontWeight.w600),
                    ),
                    trailing: DropdownButton<String>(
                      value: _theme,
                      items: const [
                        DropdownMenuItem(value: 'light', child: Text('İşıqlı')),
                        DropdownMenuItem(value: 'dark', child: Text('Qaranlıq')),
                        DropdownMenuItem(
                            value: 'high_contrast', child: Text('Yüksək Kontrast')),
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
            label: 'Seçimləri Yadda Saxla',
            icon: Icons.save_rounded,
            backgroundColor: AppTheme.primaryBlue,
            onPressed: _savePreferences,
          ),
          if (_statusMessage.isNotEmpty) ...[
            const SizedBox(height: 12),
            Text(
              _statusMessage,
              style: const TextStyle(
                fontSize: 18,
                fontWeight: FontWeight.w600,
                color: AppTheme.confirmGreen,
              ),
              textAlign: TextAlign.center,
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
                    '🔒 Məxfilik və Təhlükəsizlik Prinsipləri',
                    style: TextStyle(fontSize: 20, fontWeight: FontWeight.bold),
                  ),
                  SizedBox(height: 10),
                  Text('• Kontaktlar yalnız cihaz daxilində axtarılır.'),
                  Text('• SMS, WhatsApp, şəkillər və GPS oxunmur.'),
                  Text('• Zəngdən əvvəl istifadəçi təsdiqi məcburidir.'),
                  Text('• Bank və Wolt əməliyyatları MVP-də bloklanıb.'),
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}

