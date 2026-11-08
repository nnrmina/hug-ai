import 'package:flutter/material.dart';

import '../../../app/routes.dart';
import '../../../core/permissions/permission_service.dart';
import '../../../shared/models/assistant_response_model.dart';
import '../../contacts/data/local_contact_matcher.dart';
import '../../contacts/domain/contact_match_result.dart';
import '../../contacts/domain/local_contact_alias.dart';
import '../../contacts/presentation/contact_confirmation_screen.dart';
import '../data/voice_assistant_repository.dart';

class CallFlowResult {
  final String message;
  final bool dialerOpened;

  const CallFlowResult(this.message, {this.dialerOpened = false});
}

/// Shared "find contact → explicit confirmation → dial" flow.
/// A call is NEVER placed without the user pressing "Bəli, zəng et".
class AssistantFlow {
  final VoiceAssistantRepository repository;
  final LocalContactMatcher matcher;
  final PermissionService permissions;

  AssistantFlow({
    VoiceAssistantRepository? repository,
    LocalContactMatcher? matcher,
    PermissionService? permissions,
  })  : repository = repository ?? VoiceAssistantRepository(),
        matcher = matcher ?? LocalContactMatcher(),
        permissions = permissions ?? PermissionService();

  static const _callIntents = {'MAKE_CALL', 'EMERGENCY_CALL'};

  static bool isCallConfirmation(AssistantResponseModel r) =>
      r.needsConfirmation && _callIntents.contains(r.intent);

  Future<void> cancelQuietly(String? actionId) async {
    if (actionId == null) return;
    try {
      await repository.cancelAction(actionId);
    } catch (_) {
      // Already resolved/expired on the server — nothing else to do.
    }
  }

  Future<CallFlowResult> runCallFlow(
    BuildContext context,
    AssistantResponseModel response,
    String spokenText,
  ) async {
    final List<LocalContactAlias> candidates;

    if (response.intent == 'EMERGENCY_CALL') {
      final raw = response.actionData?['phone_number']?.toString().trim();
      final number =
          (raw != null && RegExp(r'^1\d{1,2}$').hasMatch(raw)) ? raw : '103';
      candidates = [
        LocalContactAlias(
          alias: 'təcili',
          contactId: 'emergency_$number',
          displayName: 'Təcili yardım',
          phoneNumber: number,
        ),
      ];
    } else {
      final permission = await permissions.requestContacts(context);
      if (permission != PermissionOutcome.granted) {
        await cancelQuietly(response.actionId);
        return const CallFlowResult(
            'Kontaktlara icazə verilmədi. Zəng etmək üçün kontaktlara giriş lazımdır.');
      }

      final queries = response.contactQueries;
      if (queries.isEmpty) queries.add(spokenText);
      final result = await matcher.search(queries);

      switch (result.status) {
        case ContactMatchStatus.found:
        case ContactMatchStatus.multiple:
          candidates = result.candidates;
        case ContactMatchStatus.notFound:
          await cancelQuietly(response.actionId);
          return const CallFlowResult(
              'Bu adda kontakt tapılmadı. Zəng edilmədi.');
        case ContactMatchStatus.permissionDenied:
          await cancelQuietly(response.actionId);
          return const CallFlowResult(
              'Kontaktlara icazə verilmədi. Zəng edilmədi.');
        case ContactMatchStatus.error:
          await cancelQuietly(response.actionId);
          return const CallFlowResult(
              'Kontaktları oxumaq mümkün olmadı. Zəng edilmədi.');
      }
    }

    if (!context.mounted) {
      await cancelQuietly(response.actionId);
      return const CallFlowResult('Zəng ləğv edildi.');
    }

    final outcome = await Navigator.of(context).pushNamed<CallOutcome>(
      AppRoutes.contactConfirmation,
      arguments: ContactConfirmationArgs(
        candidates: candidates,
        actionId: response.actionId,
      ),
    );

    if (outcome == null || !outcome.actionResolved) {
      await cancelQuietly(response.actionId);
    }
    return CallFlowResult(
      outcome?.message ?? 'Zəng ləğv edildi.',
      dialerOpened: outcome?.dialed ?? false,
    );
  }
}
