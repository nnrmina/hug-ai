import 'local_contact_alias.dart';

enum ContactMatchStatus { found, multiple, notFound, permissionDenied, error }

class ContactMatchResult {
  final ContactMatchStatus status;
  final List<LocalContactAlias> candidates;

  const ContactMatchResult(this.status, [this.candidates = const []]);

  ContactMatchResult.found(LocalContactAlias contact)
      : this(ContactMatchStatus.found, [contact]);

  const ContactMatchResult.multiple(List<LocalContactAlias> list)
      : this(ContactMatchStatus.multiple, list);

  const ContactMatchResult.notFound() : this(ContactMatchStatus.notFound);

  bool get hasCandidates => candidates.isNotEmpty;
}
