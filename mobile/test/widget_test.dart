import 'package:flutter_test/flutter_test.dart';
import 'package:yaxin_ai_mobile/features/contacts/data/local_contact_matcher.dart';

void main() {
  test('LocalContactMatcher resolves Azerbaijani kinship alias qızım locally', () {
    final matcher = LocalContactMatcher();
    final contact = matcher.findByAliasOrName('qızım');
    expect(contact, isNotNull);
    expect(contact!.displayName, 'Aysel Ibrahimova');
    expect(contact.contactId, 'local_contact_123');
  });
}

