import { useListState } from '@/lib/useListState';
import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import { Button, Card, Divider, Group, MultiSelect, SegmentedControl, Select, Stack, Tabs, Text } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { api } from '@/api/client';
import { useApi, useUsers } from '@/api/hooks';
import type { Page, Task } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { TaskModal } from '@/components/forms';
import { CompleteTaskModal, TaskRow } from '@/components/TasksPanel';
import { Empty, PageHeader, Pager, QueryFeedback } from '@/components/ui';
import { dayjs } from '@/lib/format';
import { TASK_TYPES } from '@/lib/labels';

const TABS = [
  { value: 'today', label: 'Сегодня' },
  { value: 'overdue', label: 'Просроченные' },
  { value: 'upcoming', label: 'Предстоящие' },
  { value: 'done', label: 'Выполненные' },
];

function groupLabel(t: Task) {
  const d = dayjs(t.due_at);
  if (t.is_overdue) return 'Просрочено';
  if (d.isToday()) return 'Сегодня';
  if (d.isSame(dayjs().add(1, 'day'), 'day')) return 'Завтра';
  if (d.isBefore(dayjs().endOf('week'))) return 'На этой неделе';
  return 'Позже';
}

export default function TasksPage() {
  const { can } = useAuth();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useListState('tab', 'today');
  const [scope, setScope] = useListState('scope', 'mine');
  const [types, setTypes] = useListState<string[]>('types', []);
  const [assignee, setAssignee] = useListState<string | null>('assignee', null);
  const [page, setPage] = useListState('page', 1);
  const [creating, setCreating] = useState(false);
  const [editing, setEditing] = useState<Task | null>(null);
  const [completing, setCompleting] = useState<Task | null>(null);
  const users = useUsers();

  useEffect(() => {
    const targetTab = params.get('tab');
    if (targetTab && TABS.some((t) => t.value === targetTab)) {
      setTab(targetTab); setTypes([]); setPage(1);
      setScope(params.get('scope') === 'all' && can('tasks.view_all') ? 'all' : 'mine');
      setAssignee(can('tasks.view_all') ? params.get('assignee') || null : null);
    }
  }, [params, can]);

  useEffect(() => {
    const openId = params.get('open');
    if (openId) {
      api.get<Task>(`/tasks/${openId}`).then(({ data }) => setEditing(data)).catch(() => undefined);
      params.delete('open');
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  const filters: Record<string, unknown> = {
    scope: assignee ? 'all' : scope, type: types, assignee_id: assignee ?? undefined, page, page_size: 50,
  };
  if (tab === 'today') Object.assign(filters, { status: ['open'], date_to: dayjs().endOf('day').toISOString() });
  if (tab === 'overdue') Object.assign(filters, { overdue: true });
  if (tab === 'upcoming') Object.assign(filters, { status: ['open'], date_from: dayjs().endOf('day').toISOString() });
  if (tab === 'done') Object.assign(filters, { status: ['done'] });
  const query = useApi<Page<Task>>(['tasks'], '/tasks', filters);
  const { data, isLoading, isError } = query;

  const grouped: [string, Task[]][] = [];
  (data?.items ?? []).forEach((t) => {
    const label = tab === 'done' ? 'Выполненные' : groupLabel(t);
    const g = grouped.find(([l]) => l === label);
    if (g) g[1].push(t);
    else grouped.push([label, [t]]);
  });

  return (
    <>
      <PageHeader title="Задачи" subtitle="Звонки, встречи, письма и подготовка КП"
        actions={<Button leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>Задача</Button>} />
      <Group justify="space-between" mb="md" wrap="wrap">
        <Tabs value={tab} onChange={(v) => { setTab(v!); setPage(1); }}>
          <Tabs.List>
            {TABS.map((t) => <Tabs.Tab key={t.value} value={t.value}>{t.label}</Tabs.Tab>)}
          </Tabs.List>
        </Tabs>
        <Group gap="xs">
          <MultiSelect placeholder="Тип" w={220} clearable value={types} onChange={setTypes} aria-label="Тип задачи"
            data={Object.entries(TASK_TYPES).map(([value, v]) => ({ value, label: v.label }))} />
          <SegmentedControl value={scope} onChange={setScope} data={[
            { value: 'mine', label: 'Мои' }, { value: 'created', label: 'Поручил я' },
            ...(can('tasks.view_all') ? [{ value: 'all', label: 'Все' }] : []),
          ]} />
          {can('tasks.view_all') && (
            <Select placeholder="Исполнитель" w={200} clearable searchable data={users.options} value={assignee}
              onChange={setAssignee} aria-label="Исполнитель" />
          )}
        </Group>
      </Group>
      <QueryFeedback query={query} hasData={!!data} />
      <Card>
        {!isLoading && !isError && !data?.items.length && <Empty text={tab === 'overdue' ? 'Просроченных задач нет 👍' : 'Задач нет'} />}
        <Stack gap="md">
          {grouped.map(([label, tasks]) => (
            <div key={label}>
              <Text size="xs" tt="uppercase" fw={700} c={label === 'Просрочено' ? 'red' : 'dimmed'} mb={4}>
                {label} · {tasks.length}
              </Text>
              <Divider mb={4} />
              {tasks.map((t) => <TaskRow key={t.id} task={t} onOpen={setEditing} onComplete={setCompleting} />)}
            </div>
          ))}
        </Stack>
      </Card>
      {data && <Pager page={page} pages={data.pages} total={data.total} pageSize={50} onPage={setPage} />}
      <TaskModal opened={creating} onClose={() => setCreating(false)} />
      <TaskModal opened={!!editing} onClose={() => setEditing(null)} task={editing} />
      <CompleteTaskModal task={completing} onClose={() => setCompleting(null)} />
    </>
  );
}
