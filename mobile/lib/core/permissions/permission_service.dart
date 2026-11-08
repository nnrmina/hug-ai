import 'package:flutter/material.dart';
import 'package:permission_handler/permission_handler.dart';

import '../constants/app_strings.dart';

enum PermissionOutcome { granted, denied, permanentlyDenied }

/// Least-privilege runtime permissions (microphone + contacts only).
/// Never requests SMS, call log, photos or location.
class PermissionService {
  Future<PermissionOutcome> requestMicrophone() =>
      _request(Permission.microphone);

  /// Shows an explanation first, then the real system permission dialog.
  Future<PermissionOutcome> requestContacts(BuildContext context) async {
    try {
      if (await Permission.contacts.isGranted) return PermissionOutcome.granted;
    } catch (_) {
      return PermissionOutcome.denied;
    }
    if (!context.mounted) return PermissionOutcome.denied;

    final agreed = await showDialog<bool>(
      context: context,
      barrierDismissible: false,
      builder: (ctx) => AlertDialog(
        title: const Text(AppStrings.contactPermissionTitle,
            style: TextStyle(fontSize: 22, fontWeight: FontWeight.w700)),
        content: const Text(AppStrings.contactPermissionMessage,
            style: TextStyle(fontSize: 18)),
        actions: [
          TextButton(
            style: TextButton.styleFrom(minimumSize: const Size(88, 56)),
            onPressed: () => Navigator.of(ctx).pop(false),
            child: const Text(AppStrings.notNowPermission,
                style: TextStyle(fontSize: 18)),
          ),
          ElevatedButton(
            style: ElevatedButton.styleFrom(minimumSize: const Size(88, 56)),
            onPressed: () => Navigator.of(ctx).pop(true),
            child: const Text(AppStrings.allowPermission,
                style: TextStyle(fontSize: 18)),
          ),
        ],
      ),
    );
    if (agreed != true) return PermissionOutcome.denied;
    return _request(Permission.contacts);
  }

  Future<bool> openSettings() => openAppSettings();

  Future<PermissionOutcome> _request(Permission permission) async {
    try {
      final status = await permission.request();
      if (status.isGranted || status.isLimited) {
        return PermissionOutcome.granted;
      }
      if (status.isPermanentlyDenied) {
        return PermissionOutcome.permanentlyDenied;
      }
      return PermissionOutcome.denied;
    } catch (_) {
      return PermissionOutcome.denied;
    }
  }
}
