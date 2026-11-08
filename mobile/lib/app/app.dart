import 'package:flutter/material.dart';
import '../core/theme/app_theme.dart';
import 'routes.dart';

class YaxinAiApp extends StatelessWidget {
  const YaxinAiApp({super.key});

  @override
  Widget build(BuildContext context) {
    return MaterialApp(
      title: 'YAXIN AI',
      debugShowCheckedModeBanner: false,
      theme: AppTheme.lightTheme,
      initialRoute: AppRoutes.home,
      routes: AppRoutes.routes,
    );
  }
}

