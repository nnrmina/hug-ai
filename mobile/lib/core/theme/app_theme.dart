import 'package:flutter/material.dart';

class AppTheme {
  static const Color primaryBlue = Color(0xFF79E024);
  static const Color confirmGreen = Color(0xFF88E836);
  static const Color dangerRed = Color(0xFFB3261E);
  static const Color backgroundLight = Color(0xFFEBF3E8);

  static ThemeData get lightTheme {
    return ThemeData(
      useMaterial3: true,
      scaffoldBackgroundColor: backgroundLight,
      colorScheme: ColorScheme.fromSeed(
        seedColor: confirmGreen,
        primary: confirmGreen,
      ),
      textTheme: const TextTheme(
        headlineMedium: TextStyle(
          fontSize: 27,
          fontWeight: FontWeight.w600,
          color: Color(0xFF111812),
        ),
        titleLarge: TextStyle(
          fontSize: 20,
          fontWeight: FontWeight.w600,
          color: Color(0xFF111812),
        ),
        bodyLarge: TextStyle(
          fontSize: 16,
          height: 1.4,
          color: Color(0xFF526354),
        ),
        bodyMedium: TextStyle(
          fontSize: 14,
          height: 1.4,
          color: Color(0xFF526354),
        ),
      ),
    );
  }
}
