import 'package:flutter/material.dart';
import '../features/home/presentation/home_screen.dart';
import '../features/voice/presentation/voice_assistant_screen.dart';
import '../features/contacts/presentation/contact_confirmation_screen.dart';
import '../features/reminders/presentation/reminders_screen.dart';
import '../features/security/presentation/digital_shield_screen.dart';
import '../features/settings/presentation/settings_screen.dart';

class AppRoutes {
  static const String home = '/';
  static const String voiceAssistant = '/voice';
  static const String contactConfirmation = '/contact-confirm';
  static const String reminders = '/reminders';
  static const String digitalShield = '/digital-shield';
  static const String settings = '/settings';

  static Map<String, WidgetBuilder> get routes => {
        home: (_) => const HomeScreen(),
        voiceAssistant: (_) => const VoiceAssistantScreen(),
        contactConfirmation: (_) => const ContactConfirmationScreen(),
        reminders: (_) => const RemindersScreen(),
        digitalShield: (_) => const DigitalShieldScreen(),
        settings: (_) => const SettingsScreen(),
      };
}
