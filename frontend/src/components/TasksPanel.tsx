import { useState } from 'react';
import { ActionIcon, Badge, Button, Checkbox, Group, Modal, Stack, Text, Textarea, Tooltip } from '@mantine/core';
import { IconAlarm, IconPlus } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Page, Task } from '@/api/types';
import { smartDate } from '@/lib/format';
import { PRIORITIES, TASK_TYPES } from '@/lib/labels';
import { TaskDefaults, TaskModal } from './forms';
import { EntityLink } from './ui';

const RELATED_URL: Record<string, string> = { deal: '/deals', company: '/companies', contact: '/contacts', lead: '/leads' };

export function CompleteTaskModal({ task, onClose }: { task: Task | null; onClose: () => void }) {
  const qc = useQueryClient();
  const [result, setResult] = useState('');
  const [saving, setSaving] = useState(false);
  const submit = async () => {
    if (!task) return;
    setSaving(true);
    try {
      await api.post(`/tasks/${task.id}/complete`, { result: result || null });
      ['tasks', 'activities', 'dashboard', 'calendar'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      notifyOk('Задача выполнена');
      setResult('');
      onClose();
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal opened={!!task} onClose={onClose} title="Завершение задачи">
      <Stack>
        <Text size="sm" fw={500}>
          {task?.title}
        </Text>
        <Textarea label="Результат" placeholder="Например: договорились о встрече во вторник" autosize minRows={3}
          value={result} onChange={(e) => setResult(e.currentTarget.value)} data-autofocus />
        <Text size="xs" c="dimmed">
          Результат попадёт в ленту взаимодействий клиента.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={submit} loading={saving} color="teal">
            Выполнено
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export function TaskRow({ task, onOpen, onComplete, showRelated = true }: {
  task: Task; onOpen: (t: Task) => void; onComplete: (t: Task) => void; showRelated?: boolean;
}) {
  const done = task.status === 'done';
  return (
    <Group wrap="nowrap" align="flex-start" gap="sm" py={6}>
      <Tooltip label={done ? 'Выполнена' : 'Отметить выполненной'}>
        <Checkbox mt={2} checked={done} disabled={done} onChange={() => onComplete(task)} radius="xl" color="teal"
          aria-label="Выполнено" />
      </Tooltip>
      <div style={{ flex: 1, minWidth: 0, cursor: 'pointer' }} onClick={() => onOpen(task)}>
        <Group gap={6} wrap="nowrap">
          <Text size="sm" fw={500} td={done ? 'line-through' : undefined} c={done ? 'dimmed' : undefined} truncate>
            {task.title}
          </Text>
        </Group>
        <Group gap={6} mt={2}>
          <Badge size="xs" color={TASK_TYPES[task.type]?.color}>
            {TASK_TYPES[task.type]?.label}
          </Badge>
          {task.priority === 'high' && (
            <Badge size="xs" color={PRIORITIES.high.color} variant="outline">
              Важно
            </Badge>
          )}
          <Text size="xs" c={task.is_overdue ? 'red' : 'dimmed'} fw={task.is_overdue ? 600 : 400}>
            {task.is_overdue && 'Просрочено · '}
            {smartDate(task.due_at)}
          </Text>
          {task.reminder_minutes && !done && <IconAlarm size={12} color="var(--mantine-color-dimmed)" />}
          {showRelated &&
            task.related.slice(0, 2).map((r) => (
              <Text size="xs" key={`${r.type}${r.id}`} truncate maw={220}>
                <EntityLink to={`${RELATED_URL[r.type]}/${r.id}`}>{r.name}</EntityLink>
              </Text>
            ))}
        </Group>
      </div>
    </Group>
  );
}

export default function TasksPanel({ defaults }: { defaults: TaskDefaults }) {
  const [editing, setEditing] = useState<Task | null>(null);
  const [creating, setCreating] = useState(false);
  const [completing, setCompleting] = useState<Task | null>(null);
  const [showDone, setShowDone] = useState(false);
  const params = {
    scope: 'all', deal_id: defaults.deal_id, company_id: defaults.company_id, contact_id: defaults.contact_id,
    lead_id: defaults.lead_id, status: showDone ? undefined : ['open'], page_size: 50,
  };
  const { data } = useApi<Page<Task>>(['tasks'], '/tasks', params);
  return (
    <Stack gap={0}>
      <Group justify="space-between" mb="xs">
        <Checkbox size="xs" label="Показать выполненные" checked={showDone}
          onChange={(e) => setShowDone(e.currentTarget.checked)} />
        <Tooltip label="Новая задача">
          <ActionIcon variant="light" onClick={() => setCreating(true)} aria-label="Новая задача">
            <IconPlus size={16} />
          </ActionIcon>
        </Tooltip>
      </Group>
      {!data?.items.length && (
        <Text size="sm" c="dimmed" py="xs">
          Нет запланированных задач.{' '}
          <Text span c="blue" style={{ cursor: 'pointer' }} onClick={() => setCreating(true)}>
            Запланировать
          </Text>
        </Text>
      )}
      {data?.items.map((t) => (
        <TaskRow key={t.id} task={t} onOpen={setEditing} onComplete={setCompleting} showRelated={false} />
      ))}
      <TaskModal opened={creating} onClose={() => setCreating(false)} defaults={defaults} />
      <TaskModal opened={!!editing} onClose={() => setEditing(null)} task={editing} />
      <CompleteTaskModal task={completing} onClose={() => setCompleting(null)} />
    </Stack>
  );
}
