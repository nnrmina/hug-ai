import 'package:flutter_contacts/flutter_contacts.dart';

import '../domain/contact_match_result.dart';
import '../domain/local_contact_alias.dart';

typedef ContactsLoader = Future<List<LocalContactAlias>> Function();

/// On-device contact search. Only the user's REAL phone contacts are used —
/// there is no built-in/fallback address book, so the app can never dial a
/// number the user did not save. Contacts never leave the device.
class LocalContactMatcher {
  final ContactsLoader _loadContacts;

  LocalContactMatcher({ContactsLoader? loadContacts})
      : _loadContacts = loadContacts ?? _loadDeviceContacts;

  static Future<List<LocalContactAlias>> _loadDeviceContacts() async {
    // Permission is requested (with an explanation) by PermissionService
    // before this is called; here we only check it.
    final granted = await FlutterContacts.requestPermission(readonly: true);
    if (!granted) throw const ContactsPermissionDenied();
    final contacts = await FlutterContacts.getContacts(withProperties: true);
    final result = <LocalContactAlias>[];
    for (final c in contacts) {
      final name = c.displayName.trim();
      if (name.isEmpty) continue;
      final seen = <String>{};
      for (final p in c.phones) {
        final number = p.number.trim();
        if (number.isEmpty) continue;
        final key = number.replaceAll(RegExp(r'[^0-9+]'), '');
        if (!seen.add(key)) continue;
        result.add(LocalContactAlias(
          alias: name,
          contactId: c.id,
          displayName: name,
          phoneNumber: number,
        ));
      }
    }
    return result;
  }

  /// Searches the device contacts for the first query that yields matches.
  Future<ContactMatchResult> search(List<String> queries) async {
    final cleaned = queries
        .map(cleanSpokenName)
        .where((q) => q.isNotEmpty)
        .toSet()
        .toList();
    if (cleaned.isEmpty) return const ContactMatchResult.notFound();

    final List<LocalContactAlias> contacts;
    try {
      contacts = await _loadContacts();
    } on ContactsPermissionDenied {
      return const ContactMatchResult(ContactMatchStatus.permissionDenied);
    } catch (_) {
      return const ContactMatchResult(ContactMatchStatus.error);
    }

    for (final q in cleaned) {
      final found = match(q, contacts);
      if (found.length == 1) return ContactMatchResult.found(found.first);
      if (found.length > 1) return ContactMatchResult.multiple(found);
    }
    return const ContactMatchResult.notFound();
  }

  /// Azerbaijani-aware case folding: İ→i, I→ı, plus a loose ASCII fold so
  /// "Aysel"/"Aysəl" or STT spelling variants still compare equal.
  static String fold(String s) {
    final lower =
        s.replaceAll('İ', 'i').replaceAll('I', 'ı').toLowerCase().trim();
    const map = {
      'ə': 'e', 'ı': 'i', 'i̇': 'i', 'ö': 'o', 'ü': 'u',
      'ğ': 'g', 'ş': 's', 'ç': 'c',
    };
    var out = lower;
    map.forEach((k, v) => out = out.replaceAll(k, v));
    out = out.replaceAll('̇', ''); // stray combining dot
    out = out.replaceAll(RegExp(r'''[.,!?;:"'«»()\-]'''), ' ');
    return out.replaceAll(RegExp(r'\s+'), ' ').trim();
  }

  /// Removes wake words and call verbs: "Yaxın, Almaza zəng et" → "almaza".
  static String cleanSpokenName(String raw) {
    var s = fold(raw);
    s = s.replaceAll(
        RegExp(r'^((yaxin|salam|zehmet olmasa|xahis edirem)\s*)+'), '');
    s = s.replaceAll(
        RegExp(
            r'(^|\s+)(nomresini\s+)?(zeng\s*(et|edin|vur|ele|eyle)|yig|yigin|ile\s+danis)\b.*$'),
        '');
    return s.trim();
  }

  /// Candidate spellings for an inflected spoken name, most literal first:
  /// "almaza" → ["almaza", "almaz"], "leylaya" → ["leylaya", "leyla", ...].
  static List<String> nameVariants(String cleaned) {
    final s = cleaned.trim();
    if (s.isEmpty) return const [];
    final variants = <String>[s];
    if (s.length > 4 && (s.endsWith('ya') || s.endsWith('ye'))) {
      variants.add(s.substring(0, s.length - 2));
    }
    if (s.length > 3 && (s.endsWith('a') || s.endsWith('e'))) {
      variants.add(s.substring(0, s.length - 1));
    }
    // Genitive: "almazin" (Almazın), "leylanin" (Leylanın).
    if (s.length > 5 && (s.endsWith('nin') || s.endsWith('nun'))) {
      variants.add(s.substring(0, s.length - 3));
    }
    if (s.length > 4 && (s.endsWith('in') || s.endsWith('un'))) {
      variants.add(s.substring(0, s.length - 2));
    }
    return variants.toSet().toList();
  }

  /// Pure matching logic (unit-testable).
  /// 1) exact full-name or exact word match, 2) prefix match.
  /// Never matches by arbitrary substring. Returns ALL equally good matches
  /// so the caller can ask the user to choose.
  static List<LocalContactAlias> match(
    String query,
    List<LocalContactAlias> contacts,
  ) {
    final variants = nameVariants(cleanSpokenName(query));
    if (variants.isEmpty) return const [];

    final usable = contacts
        .where((c) =>
            c.displayName.trim().isNotEmpty && c.phoneNumber.trim().isNotEmpty)
        .toList();

    for (final v in variants) {
      final exact = usable.where((c) {
        final name = fold(c.displayName);
        return name == v || name.split(' ').contains(v);
      }).toList();
      if (exact.isNotEmpty) return _dedupe(exact);
    }

    for (final v in variants) {
      if (v.length < 3) continue;
      final prefix = usable.where((c) {
        final name = fold(c.displayName);
        return name.startsWith(v) ||
            name.split(' ').any((word) => word.startsWith(v));
      }).toList();
      if (prefix.isNotEmpty) return _dedupe(prefix);
    }
    return const [];
  }

  static List<LocalContactAlias> _dedupe(List<LocalContactAlias> list) {
    final seen = <String>{};
    return list
        .where((c) => seen.add('${c.contactId}|${c.phoneNumber}'))
        .toList();
  }
}

class ContactsPermissionDenied implements Exception {
  const ContactsPermissionDenied();
}
