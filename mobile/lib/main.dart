import 'package:flutter/material.dart';
import 'package:flutter_riverpod/flutter_riverpod.dart';

import 'app/app.dart';
import 'core/config/app_config.dart';

void main() {
  WidgetsFlutterBinding.ensureInitialized();

  // Release builds must talk to the backend over HTTPS only. Fail loudly at
  // start-up instead of silently sending data over plain HTTP (which Android
  // would block anyway via network_security_config).
  final configError = AppConfig.configError;
  if (configError != null) {
    debugPrint('YAXIN AI configuration error: $configError');
    runApp(_ConfigErrorApp(message: configError));
    return;
  }

  runApp(
    const ProviderScope(
      child: YaxinAiApp(),
    ),
  );
}

class _ConfigErrorApp extends StatelessWidget {
  final String message;

  const _ConfigErrorApp({required this.message});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      debugShowCheckedModeBanner: false,
      home: Scaffold(
        body: SafeArea(
          child: Padding(
            padding: const EdgeInsets.all(24),
            child: Center(
              child: Column(
                mainAxisSize: MainAxisSize.min,
                children: [
                  const Icon(Icons.error_outline_rounded,
                      size: 72, color: Color(0xFFB3261E)),
                  const SizedBox(height: 16),
                  const Text(
                    'Tətbiq düzgün qurulmayıb',
                    style: TextStyle(fontSize: 24, fontWeight: FontWeight.w700),
                    textAlign: TextAlign.center,
                  ),
                  const SizedBox(height: 12),
                  Text(message,
                      style: const TextStyle(fontSize: 18),
                      textAlign: TextAlign.center),
                ],
              ),
            ),
          ),
        ),
      ),
    );
  }
}
