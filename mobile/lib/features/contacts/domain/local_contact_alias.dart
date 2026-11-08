class LocalContactAlias {
  final String alias;
  final String contactId;
  final String displayName;
  final String phoneNumber;

  const LocalContactAlias({
    required this.alias,
    required this.contactId,
    required this.displayName,
    required this.phoneNumber,
  });

  Map<String, dynamic> toJson() => {
        'alias': alias,
        'contact_id': contactId,
        'display_name': displayName,
        'phone_number': phoneNumber,
      };
}

