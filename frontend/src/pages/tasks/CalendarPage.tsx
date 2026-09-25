import { useState } from 'react';
import FullCalendar from '@fullcalendar/react';
import dayGridPlugin from '@fullcalendar/daygrid';
import timeGridPlugin from '@fullcalendar/timegrid';
import interactionPlugin from '@fullcalendar/interaction';
import ruLocale from '@fullcalendar/core/locales/ru';
import type { EventDropArg } from '@fullcalendar/core';
import { Button, Card, CopyButton, Group, Modal, Select, Stack, Text, TextInput } from '@mantine/core';
import { IconCalendarShare } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi, useUsers } from '@/api/hooks';
import type { Page, Task } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { TaskModal } from '@/components/forms';
import { PageHeader } from '@/components/ui';

const COLORS: Record<string, string> = {
  call: '#1c7ed6', meeting: '#7048e8', email: '#1098ad', proposal: '#f76707', other: '#868e96',
};

export default function CalendarPage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const users = useUsers();
  const [range, setRange] = useState<{ from: string; to: string } | null>(null);
  const [assignee, setAssignee] = useState<string | null>(null);
  const [editing, setEditing] = useState<Task | null>(null);
  const [creatingAt, setCreatingAt] = useState<Date | null>(null);
  const [icsOpen, setIcsOpen] = useState(false);
  const { data } = useApi<Page<Task>>(['calendar'], range ? '/tasks' : null, {
    scope: assignee ? 'all' : 'mine', assignee_id: assignee ?? undefined, date_from: range?.from, date_to: range?.to,
    page_size: 500, status: ['open', 'done'],
  });
  const { data: ics } = useApi<{ url: string }>(['ics'], icsOpen ? '/tasks/ics-url' : null);

  const events = (data?.items ?? []).map((t) => ({
    id: String(t.id),
    title: t.title + (t.related[0] ? ` — ${t.related[0].name}` : ''),
    start: t.due_at,
    end: new Date(new Date(t.due_at).getTime() + t.duration_minutes * 60000).toISOString(),
    backgroundColor: t.status === 'done' ? '#adb5bd' : t.is_overdue ? '#e03131' : COLORS[t.type],
    borderColor: 'transparent',
    extendedProps: { task: t },
  }));

  const onDrop = async (arg: EventDropArg) => {
    const t = arg.event.extendedProps.task as Task;
    try {
      await api.patch(`/tasks/${t.id}`, { due_at: arg.event.start?.toISOString() });
      notifyOk('Задача перенесена');
      qc.invalidateQueries({ queryKey: ['calendar'] });
      qc.invalidateQueries({ queryKey: ['tasks'] });
    } catch (e) {
      notifyError(e);
      arg.revert();
    }
  };

  return (
    <>
      <PageHeader title="Календарь" subtitle="Задачи и встречи: день, неделя, месяц"
        actions={
          <>
            {can('tasks.view_all') && (
              <Select placeholder="Мой календарь" w={220} clearable searchable data={users.options} value={assignee}
                onChange={setAssignee} aria-label="Сотрудник" />
            )}
            <Button variant="default" leftSection={<IconCalendarShare size={16} />} onClick={() => setIcsOpen(true)}>
              Синхронизация
            </Button>
          </>
        } />
      <Card>
        <FullCalendar
          plugins={[dayGridPlugin, timeGridPlugin, interactionPlugin]}
          locale={ruLocale}
          initialView="timeGridWeek"
          headerToolbar={{ left: 'prev,next today', center: 'title', right: 'timeGridDay,timeGridWeek,dayGridMonth' }}
          height="calc(100vh - 230px)"
          slotMinTime="07:00:00"
          slotMaxTime="21:00:00"
          nowIndicator
          allDaySlot={false}
          editable
          selectable
          events={events}
          datesSet={(arg) => setRange({ from: arg.start.toISOString(), to: arg.end.toISOString() })}
          eventClick={(arg) => setEditing(arg.event.extendedProps.task as Task)}
          eventDrop={onDrop}
          dateClick={(arg) => setCreatingAt(arg.date)}
          businessHours={{ daysOfWeek: [1, 2, 3, 4, 5], startTime: '09:00', endTime: '18:00' }}
        />
      </Card>
      <TaskModal opened={!!editing} onClose={() => setEditing(null)} task={editing} />
      <TaskModal opened={!!creatingAt} onClose={() => setCreatingAt(null)}
        defaults={creatingAt ? { due_at: creatingAt, type: 'meeting' } : undefined} />
      <Modal opened={icsOpen} onClose={() => setIcsOpen(false)} title="Синхронизация с внешним календарём">
        <Stack>
          <Text size="sm">
            Подпишитесь на эту ссылку в Google Calendar («Другие календари → Добавить по URL») или Outlook
            («Добавить календарь → Из Интернета») — задачи CRM будут отображаться автоматически.
          </Text>
          <TextInput value={ics?.url ?? 'Загрузка…'} readOnly aria-label="Ссылка на календарь" />
          <Group justify="flex-end">
            <CopyButton value={ics?.url ?? ''}>
              {({ copied, copy }) => <Button onClick={copy} color={copied ? 'teal' : 'blue'}>{copied ? 'Скопировано' : 'Копировать ссылку'}</Button>}
            </CopyButton>
          </Group>
          <Text size="xs" c="dimmed">Ссылка персональная — не передавайте её другим людям.</Text>
        </Stack>
      </Modal>
    </>
  );
}
