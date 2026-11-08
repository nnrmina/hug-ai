import 'package:flutter/material.dart';

class AppTheme {
  /// Button / filled-surface green. White text on it has ~5.1:1 contrast.
  static const Color primaryGreen = Color(0xFF2E7D32);

  /// Confirmation ("Bəli") button green — same accessible shade.
  static const Color confirmGreen = Color(0xFF2E7D32);

  /// Green for text on the light background (~7:1 contrast).
  static const Color textAccentGreen = Color(0xFF1B5E20);

  static const Color warningAmber = Color(0xFF8A5A00);
  static const Color dangerRed = Color(0xFFB3261E);
  static const Color backgroundLight = Color(0xFFEBF3E8);
  static const Color textPrimary = Color(0xFF111812);
  static const Color textSecondary = Color(0xFF3F4E41);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: backgroundLight,
      colorScheme: ColorScheme.fromSeed(
        seedColor: primaryGreen,
        primary: primaryGreen,
        onPrimary: Colors.white,
      ),
      materialTapTargetSize: MaterialTapTargetSize.padded,
      appBarTheme: const AppBarTheme(
        backgroundColor: backgroundLight,
        foregroundColor: textPrimary,
        titleTextStyle: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w700,
          color: textPrimary,
        ),
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          fontSize: 28,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        titleLarge: TextStyle(
          fontSize: 22,
          fontWeight: FontWeight.w600,
          color: textPrimary,
        ),
        bodyLarge: TextStyle(
          fontSize: 18,
          height: 1.4,
          color: textSecondary,
        ),
        bodyMedium: TextStyle(
          fontSize: 16,
          height: 1.4,
          color: textSecondary,
        ),
      ),
    );
  }
}
