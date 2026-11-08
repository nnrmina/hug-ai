import 'dart:convert';

import 'package:flutter/material.dart';
import 'package:flutter_test/flutter_test.dart';
import 'package:http/http.dart' as http;
import 'package:http/testing.dart';
import 'package:yaxin_ai_mobile/core/auth/device_auth_service.dart';
import 'package:yaxin_ai_mobile/core/network/api_client.dart';
import 'package:yaxin_ai_mobile/features/contacts/data/local_contact_matcher.dart';
import 'package:yaxin_ai_mobile/features/contacts/domain/contact_match_result.dart';
import 'package:yaxin_ai_mobile/features/contacts/domain/local_contact_alias.dart';
import 'package:yaxin_ai_mobile/features/contacts/presentation/contact_confirmation_screen.dart';
import 'package:yaxin_ai_mobile/features/voice/data/voice_assistant_repository.dart';

LocalContactAlias c(String id, String name, String phone) => LocalContactAlias(
    alias: name, contactId: id, displayName: name, phoneNumber: phone);

final _contacts = [
  c('1', 'Almaz Məmmədova', '+10000000001'),
  c('2', 'Almaz Xala', '+10000000002'),
  c('3', 'Leyla Həsənova', '+10000000003'),
  c('4', 'Natali', '+10000000004'),
  c('5', '', '+10000000005'),
  c('6', 'Qızım', '+10000000006'),
  c('7', 'Kamran Əliyev', '+10000000007'),
];

class _FakeAuth implements AuthTokenProvider {
  @override
  Future<String> getToken() async => 'tok';
  @override
  Future<String> refreshToken() async => 'tok2';
}

void main() {
  group('LocalContactMatcher.match', () {
    test('exact full name wins over word match', () {
      final r = LocalContactMatcher.match('Almaz Xala', _contacts);
      expect(r.map((e) => e.contactId), ['2']);
    });

    test('ambiguous first name returns all candidates (user must choose)', () {
      final r = LocalContactMatcher.match('Almaza zəng et', _contacts);
      expect(r.map((e) => e.contactId).toSet(), {'1', '2'});
    });

    test('dative suffix and kinship alias', () {
      expect(LocalContactMatcher.match('Leylaya zəng et', _contacts)
          .single.contactId, '3');
      expect(LocalContactMatcher.match('qızıma zəng et', _contacts)
          .single.contactId, '6');
    });

    test('prefix match but never arbitrary substring', () {
      expect(LocalContactMatcher.match('Kamr', _contacts).single.contactId,
          '7');
      // "ali" is inside "Natali" but must NOT match.
      expect(LocalContactMatcher.match('ali', _contacts), isEmpty);
    });

    test('empty display names are skipped', () {
      expect(LocalContactMatcher.match('', _contacts), isEmpty);
    });
  });

  group('LocalContactMatcher.search', () {
    test('no device contacts → notFound (no built-in fallback book)', () async {
      final matcher = LocalContactMatcher(loadContacts: () async => []);
      final r = await matcher.search(['qızım']);
      expect(r.status, ContactMatchStatus.notFound);
      expect(r.candidates, isEmpty);
    });

    test('permission denied is reported', () async {
      final matcher = LocalContactMatcher(
          loadContacts: () async => throw const ContactsPermissionDenied());
      final r = await matcher.search(['Almaz']);
      expect(r.status, ContactMatchStatus.permissionDenied);
    });
  });

  group('ContactConfirmationScreen', () {
    testWidgets('without arguments shows an error and never offers to call',
        (tester) async {
      await tester.pumpWidget(const MaterialApp(
        home: ContactConfirmationScreen(),
      ));
      await tester.pump();
      expect(find.textContaining('Bu adda kontakt tapılmadı'), findsOneWidget);
      expect(find.text('Bəli, zəng et'), findsNothing);
    });

    testWidgets('several matches → list to choose from, no auto-pick',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: ContactConfirmationScreen(
          args: ContactConfirmationArgs(candidates: _contacts.sublist(0, 2)),
        ),
      ));
      await tester.pump();
      expect(find.text('Bəli, zəng et'), findsNothing);
      expect(find.text('Almaz Xala'), findsOneWidget);
      await tester.tap(find.text('Almaz Xala'));
      await tester.pumpAndSettle();
      expect(find.text('Bəli, zəng et'), findsOneWidget);
      await tester.pump(const Duration(seconds: 10)); // flush TTS timeouts
    });

    testWidgets('409 on confirm → friendly message, dialer NOT opened',
        (tester) async {
      var dialed = false;
      final api = ApiClient(
        baseUrl: 'http://test/api/v1',
        auth: _FakeAuth(),
        client: MockClient((req) async => http.Response(
              jsonEncode({'detail': 'not awaiting confirmation'}),
              409,
            )),
      );
      final repo = VoiceAssistantRepository(apiClient: api);
      await tester.pumpWidget(MaterialApp(
        home: ContactConfirmationScreen(
          args: ContactConfirmationArgs(
              candidates: [_contacts[2]], actionId: 'a1'),
          repository: repo,
          dialer: (_) async => dialed = true,
        ),
      ));
      await tester.pump();
      await tester.tap(find.text('Bəli, zəng et'));
      await tester.pumpAndSettle();
      expect(dialed, isFalse);
      expect(find.textContaining('artıq icra olunub'), findsOneWidget);
    });

    testWidgets('dialer failure shows an error instead of "calling"',
        (tester) async {
      await tester.pumpWidget(MaterialApp(
        home: ContactConfirmationScreen(
          args: ContactConfirmationArgs(candidates: [_contacts[2]]),
          dialer: (_) async => false,
        ),
      ));
      await tester.pump();
      await tester.tap(find.text('Bəli, zəng et'));
      await tester.pumpAndSettle();
      expect(find.textContaining('Nömrə yığıcı açıla bilmədi'), findsOneWidget);
    });
  });
}
