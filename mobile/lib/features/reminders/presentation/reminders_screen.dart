import 'package:flutter/material.dart';

import '../../../core/errors/app_exception.dart';
import '../../../core/theme/app_theme.dart';
import '../../../shared/widgets/accessible_action_button.dart';
import '../data/reminder_remote_repository.dart';
import '../domain/reminder_entity.dart';

class RemindersScreen extends StatefulWidget {
  final ReminderRemoteRepository? repository;

  const RemindersScreen({super.key, this.repository});

  @override
  State<RemindersScreen> createState() => _RemindersScreenState();
}

class _RemindersScreenState extends State<RemindersScreen> {
  late final ReminderRemoteRepository _repository =
      widget.repository ?? ReminderRemoteRepository();

  List<ReminderEntity> _reminders = const [];
  bool _loading = true;
  String? _error;

  @override
  void initState() {
    super.initState();
    _load();
  }

  Future<void> _load() async {
    setState(() {
      _loading = true;
      _error = null;
    });
    try {
      final list = await _repository.fetchReminders();
      list.sort((a, b) => a.scheduledAt.compareTo(b.scheduledAt));
      if (!mounted) return;
      setState(() {
        _reminders = list;
        _loading = false;
      });
    } on AppException catch (e) {
      if (!mounted) return;
      setState(() {
        _error = e.message;
        _loading = false;
      });
    } catch (_) {
      if (!mounted) return;
      setState(() {
        _error = 'Xatırlatmaları yükləmək mümkün olmadı.';
        _loading = false;
      });
    }
  }

  String _two(int v) => v.toString().padLeft(2, '0');

  String _format(DateTime dt) {
    final d = dt.toLocal();
    return '${_two(d.day)}.${_two(d.month)}.${d.year}  ${_two(d.hour)}:${_two(d.minute)}';
  }

  String _statusLabel(String status) {
    switch (status) {
      case 'completed':
        return 'Tamamlanıb';
      case 'cancelled':
        return 'Ləğv edilib';
      default:
        return 'Gözləyir';
    }
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      appBar: AppBar(title: const Text('Xatırlatmalarım')),
      body: SafeArea(child: _buildBody(context)),
    );
  }

  Widget _buildBody(BuildContext context) {
    if (_loading) {
      return const Center(child: CircularProgressIndicator());
    }
    if (_error != null) {
      return ListView(
        padding: const EdgeInsets.all(24),
        children: [
          const Icon(Icons.cloud_off_rounded,
              size: 64, color: AppTheme.dangerRed),
          const SizedBox(height: 16),
          Text(_error!,
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center),
          const SizedBox(height: 24),
          AccessibleActionButton(
            label: 'Yenidən cəhd et',
            icon: Icons.refresh_rounded,
            backgroundColor: AppTheme.primaryGreen,
            onPressed: _load,
          ),
        ],
      );
    }
    if (_reminders.isEmpty) {
      return RefreshIndicator(
        onRefresh: _load,
        child: ListView(
          padding: const EdgeInsets.all(24),
          children: [
            const Icon(Icons.alarm_off_rounded,
                size: 64, color: AppTheme.textSecondary),
            const SizedBox(height: 16),
            Text(
              'Hələ xatırlatma yoxdur.\nYaratmaq üçün deyin: "Sabah saat 10-da dərmanımı xatırlat".',
              style: Theme.of(context).textTheme.titleLarge,
              textAlign: TextAlign.center,
            ),
          ],
        ),
      );
    }
    return RefreshIndicator(
      onRefresh: _load,
      child: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: _reminders.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final item = _reminders[index];
          return Card(
            elevation: 2,
            child: ListTile(
              contentPadding: const EdgeInsets.all(16),
              leading: const Icon(Icons.alarm_on_rounded,
                  size: 36, color: AppTheme.textAccentGreen),
              title: Text(item.title,
                  style: Theme.of(context).textTheme.titleLarge),
              subtitle: Text(
                'Vaxt: ${_format(item.scheduledAt)}\n${_statusLabel(item.status)}',
                style: Theme.of(context).textTheme.bodyLarge,
              ),
            ),
          );
        },
      ),
    );
  }
}
