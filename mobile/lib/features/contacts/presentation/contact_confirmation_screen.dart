import 'package:flutter/material.dart';
import 'package:url_launcher/url_launcher.dart';
import '../../../core/constants/app_strings.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';
import '../data/local_contact_matcher.dart';
import '../domain/local_contact_alias.dart';

class ContactConfirmationScreen extends StatelessWidget {
  final LocalContactAlias? selectedContact;

  const ContactConfirmationScreen({super.key, this.selectedContact});

  Future<void> _openDialer(BuildContext context, String phoneNumber) async {
    final uri = Uri(scheme: 'tel', path: phoneNumber);
    if (await canLaunchUrl(uri)) {
      await launchUrl(uri);
    } else if (context.mounted) {
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Zəng edilir: $phoneNumber')),
      );
    }
  }

  @override
  Widget build(BuildContext context) {
    final routeArg = ModalRoute.of(context)?.settings.arguments;
    final matcher = LocalContactMatcher();
    final LocalContactAlias contact = selectedContact ??
        (routeArg is LocalContactAlias
            ? routeArg
            : (routeArg is String
                ? (matcher.findByAliasOrName(routeArg) ??
                    matcher.findByAliasOrName('almaz')!)
                : matcher.findByAliasOrName('almaz')!));

    return Scaffold(
      appBar: AppBar(title: const Text('AI Agent — Zəng Ekranı')),
      body: Padding(
        padding: const EdgeInsets.all(24.0),
        child: Column(
          mainAxisAlignment: MainAxisAlignment.spaceBetween,
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
                      radius: 48,
                      backgroundColor: AppTheme.confirmGreen,
                      child: Icon(Icons.phone_in_talk_rounded,
                          size: 52, color: Colors.white),
                    ),
                    const SizedBox(height: 16),
                    const Text(
                      'Kontakt tapıldı:',
                      style: TextStyle(fontSize: 18, color: Colors.black54),
                    ),
                    const SizedBox(height: 6),
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
                    Text(
                      '"${contact.displayName}" nömrəsinə zəng edilir...',
                      style: const TextStyle(
                        fontSize: 20,
                        fontWeight: FontWeight.w600,
                      ),
                      textAlign: TextAlign.center,
                    ),
                  ],
                ),
              ),
            ),
            Column(
              children: [
                AccessibleActionButton(
                  label: '${contact.displayName} — Zəng Et',
                  icon: Icons.call_rounded,
                  backgroundColor: AppTheme.confirmGreen,
                  onPressed: () => _openDialer(context, contact.phoneNumber),
                ),
                const SizedBox(height: 12),
                AccessibleActionButton(
                  label: AppStrings.cancelButton,
                  icon: Icons.call_end_rounded,
                  backgroundColor: AppTheme.dangerRed,
                  onPressed: () => Navigator.pop(context),
                ),
              ],
            ),
          ],
        ),
      ),
    );
  }
}
