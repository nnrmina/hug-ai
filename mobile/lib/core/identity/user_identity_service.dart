import 'package:flutter/foundation.dart';
import 'package:shared_preferences/shared_preferences.dart';
import 'package:uuid/uuid.dart';

/// Random, anonymous UUID v4 for this installation. Since JWT auth it is only
/// sent as `legacy_user_id` to POST /auth/device (the backend binds it once,
/// so reminders created before JWT stay with this device).
/// Generated once and persisted with shared_preferences.
class UserIdentityService {
  static const String _prefsKey = 'yaxin_install_user_id';
  static Future<String>? _cached;

  static Future<String> getUserId() {
    return _cached ??= _loadOrCreate().catchError((Object e) {
      _cached = null; // allow a retry next time
      throw e;
    });
  }

  static Future<String> _loadOrCreate() async {
    final prefs = await SharedPreferences.getInstance();
    final existing = prefs.getString(_prefsKey);
    if (existing != null && Uuid.isValidUUID(fromString: existing)) {
      return existing;
    }
    final id = const Uuid().v4();
    await prefs.setString(_prefsKey, id);
    return id;
  }

  @visibleForTesting
  static void resetCache() => _cached = null;
}
