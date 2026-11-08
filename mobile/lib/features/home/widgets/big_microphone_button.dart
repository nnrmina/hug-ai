import 'package:flutter/material.dart';

import '../../../core/theme/app_theme.dart';

/// Large glossy green microphone orb.
class BigMicrophoneButton extends StatelessWidget {
  final bool isListening;
  final VoidCallback? onTap;

  const BigMicrophoneButton({
    super.key,
    required this.isListening,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    final size = isListening ? 186.0 : 176.0;
    return Semantics(
      button: true,
      enabled: onTap != null,
      label: isListening
          ? 'Mikrofon: dinləyirəm. Dayandırmaq üçün toxunun'
          : 'Mikrofon. Danışmaq üçün toxunun',
      excludeSemantics: true,
      child: Column(
        mainAxisSize: MainAxisSize.min,
        children: [
          GestureDetector(
            onTap: onTap,
            child: AnimatedContainer(
              duration: const Duration(milliseconds: 280),
              width: size,
              height: size,
              decoration: BoxDecoration(
                shape: BoxShape.circle,
                gradient: const RadialGradient(
                  center: Alignment(-0.32, -0.44),
                  radius: 0.95,
                  colors: [
                    Color(0xFFFFFFFF),
                    Color(0xFFE2FFCE),
                    Color(0xFF91EE80),
                    Color(0xFF4AD64D),
                    Color(0xFF72EB6C),
                  ],
                  stops: [0.0, 0.22, 0.52, 0.82, 1.0],
                ),
                boxShadow: [
                  BoxShadow(
                    color: const Color(0xFF60D45C)
                        .withValues(alpha: isListening ? 0.5 : 0.28),
                    blurRadius: isListening ? 42 : 32,
                    spreadRadius: isListening ? 12 : 2,
                    offset: const Offset(0, 14),
                  ),
                ],
              ),
              child: Icon(
                isListening ? Icons.graphic_eq_rounded : Icons.mic_rounded,
                size: 72,
                color: AppTheme.textAccentGreen,
              ),
            ),
          ),
          const SizedBox(height: 8),
          // Soft mirror reflection below orb
          Container(
            width: 154,
            height: 40,
            decoration: BoxDecoration(
              borderRadius: BorderRadius.circular(80),
              gradient: RadialGradient(
                center: const Alignment(0, -0.6),
                radius: 0.85,
                colors: [
                  const Color(0xFF80E078).withValues(alpha: 0.38),
                  const Color(0xFFA8EC9E).withValues(alpha: 0.14),
                  Colors.transparent,
                ],
              ),
            ),
          ),
        ],
      ),
    );
  }
}
