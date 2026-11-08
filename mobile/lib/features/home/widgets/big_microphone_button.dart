import 'package:flutter/material.dart';

/// 3D Glossy Green AI Orb with soft reflection underneath (matches reference design).
class BigMicrophoneButton extends StatelessWidget {
  final bool isListening;
  final VoidCallback onTap;

  const BigMicrophoneButton({
    super.key,
    required this.isListening,
    required this.onTap,
  });

  @override
  Widget build(BuildContext context) {
    return Column(
      mainAxisSize: MainAxisSize.min,
      children: [
        GestureDetector(
          onTap: onTap,
          child: AnimatedContainer(
            duration: const Duration(milliseconds: 280),
            width: isListening ? 186 : 176,
            height: isListening ? 186 : 176,
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
                      .withOpacity(isListening ? 0.5 : 0.28),
                  blurRadius: isListening ? 42 : 32,
                  spreadRadius: isListening ? 12 : 2,
                  offset: const Offset(0, 14),
                ),
              ],
            ),
          ),
        ),
        const SizedBox(height: 8),
        // Soft mirror reflection below orb
        Container(
          width: 154,
          height: 54,
          decoration: BoxDecoration(
            borderRadius: BorderRadius.circular(80),
            gradient: RadialGradient(
              center: const Alignment(0, -0.6),
              radius: 0.85,
              colors: [
                const Color(0xFF80E078).withOpacity(0.38),
                const Color(0xFFA8EC9E).withOpacity(0.14),
                Colors.transparent,
              ],
            ),
          ),
        ),
      ],
    );
  }
}
