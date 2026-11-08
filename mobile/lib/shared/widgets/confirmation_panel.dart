import 'package:flutter/material.dart';

import '../../core/constants/app_strings.dart';
import '../../core/theme/app_theme.dart';
import 'accessible_action_button.dart';

/// Explicit yes/no confirmation. Nothing happens until a button is pressed —
/// silence or a timeout never counts as "yes".
class ConfirmationPanel extends StatelessWidget {
  final String message;
  final VoidCallback onConfirm;
  final VoidCallback onCancel;
  final bool busy;
  final String confirmLabel;

  const ConfirmationPanel({
    super.key,
    required this.message,
    required this.onConfirm,
    required this.onCancel,
    this.busy = false,
    this.confirmLabel = AppStrings.confirmButton,
  });

  @override
  Widget build(BuildContext context) {
    return Card(
      elevation: 3,
      color: Colors.white,
      shape: RoundedRectangleBorder(borderRadius: BorderRadius.circular(20)),
      child: Padding(
        padding: const EdgeInsets.all(20),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.stretch,
          children: [
            Semantics(
              liveRegion: true,
              child: Text(
                message,
                style: const TextStyle(
                  fontSize: 20,
                  fontWeight: FontWeight.w600,
                  color: AppTheme.textPrimary,
                ),
                textAlign: TextAlign.center,
              ),
            ),
            const SizedBox(height: 20),
            if (busy)
              const Center(child: CircularProgressIndicator())
            else ...[
              AccessibleActionButton(
                label: confirmLabel,
                icon: Icons.check_rounded,
                backgroundColor: AppTheme.confirmGreen,
                onPressed: onConfirm,
              ),
              const SizedBox(height: 12),
              AccessibleActionButton(
                label: AppStrings.rejectButton,
                icon: Icons.close_rounded,
                backgroundColor: AppTheme.dangerRed,
                semanticsLabel: 'Xeyr, ləğv et',
                onPressed: onCancel,
              ),
            ],
          ],
        ),
      ),
    );
  }
}
