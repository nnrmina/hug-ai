import 'package:flutter/material.dart';
import '../domain/reminder_entity.dart';

class RemindersScreen extends StatelessWidget {
  const RemindersScreen({super.key});

  @override
  Widget build(BuildContext context) {
    final demoReminders = [
      ReminderEntity(
        id: 'rem-1',
        title: 'Qızıma zəng et',
        scheduledAt: DateTime(2026, 11, 9, 10, 0),
      ),
      ReminderEntity(
        id: 'rem-2',
        title: 'Dərman qəbulu (vaxt xatırlatması)',
        scheduledAt: DateTime(2026, 11, 8, 20, 0),
      ),
    ];

    return Scaffold(
      appBar: AppBar(title: const Text('Xatırlatmalarım')),
      body: ListView.separated(
        padding: const EdgeInsets.all(20),
        itemCount: demoReminders.length,
        separatorBuilder: (_, __) => const SizedBox(height: 12),
        itemBuilder: (context, index) {
          final item = demoReminders[index];
          return Card(
            elevation: 2,
            child: ListTile(
              contentPadding: const EdgeInsets.all(16),
              leading: const Icon(Icons.alarm_on_rounded, size: 36),
              title: Text(
                item.title,
                style: Theme.of(context).textTheme.titleLarge,
              ),
              subtitle: Text(
                'Vaxt: ${item.scheduledAt.day.toString().padLeft(2, '0')}.${item.scheduledAt.month.toString().padLeft(2, '0')}.${item.scheduledAt.year} '
                '${item.scheduledAt.hour.toString().padLeft(2, '0')}:${item.scheduledAt.minute.toString().padLeft(2, '0')} (${item.timezone})',
                style: Theme.of(context).textTheme.bodyMedium,
              ),
            ),
          );
        },
      ),
    );
  }
}

