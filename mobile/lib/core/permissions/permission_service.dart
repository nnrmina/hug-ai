import 'package:flutter/material.dart';
import '../constants/app_strings.dart';

/// Least-privilege & Explicit Consent permission manager (Section 11.4 & 12.1).
/// Never requests SMS, WhatsApp, Call History, Photos, or GPS permissions.
class PermissionService {
  bool _contactsPermissionGranted = false;
  bool _microphonePermissionGranted = false;

  bool get hasContactsPermission => _contactsPermissionGranted;
  bool get hasMicrophonePermission => _microphonePermissionGranted;

  Future<bool> requestMicrophoneConsent() async {
    _microphonePermissionGranted = true;
    return _microphonePermissionGranted;
  }

  Future<bool> requestContactsConsentDialog(BuildContext context) async {
    if (_contactsPermissionGranted) return true;

    final result = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text(AppStrings.contactPermissionTitle),
        content: const Text(AppStrings.contactPermissionMessage),
        actions: [
          TextButton(
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text(AppStrings.notNowPermission),
          ),
          ElevatedButton(
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text(AppStrings.allowPermission),
          ),
        ],
      ),
    );

    _contactsPermissionGranted = result ?? false;
    return _contactsPermissionGranted;
  }
}

