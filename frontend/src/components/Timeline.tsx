import { useState } from 'react';
import {
  ActionIcon,
  Anchor,
  Badge,
  Box,
  Button,
  Group,
  Loader,
  SegmentedControl,
  Stack,
  Text,
  Textarea,
  ThemeIcon,
  Timeline as MTimeline,
  Tooltip,
} from '@mantine/core';
import {
  IconArrowRight,
  IconCash,
  IconCheck,
  IconFile,
  IconFileInvoice,
  IconFileText,
  IconMail,
  IconMailOpened,
  IconNote,
  IconPencil,
  IconPhone,
  IconPhoneIncoming,
  IconPlus,
  IconTransform,
  IconTrash,
  IconUsers,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Activity, Page } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { dateTime, smartDate } from '@/lib/format';
import { FIELD_LABELS } from '@/lib/fieldLabels';
import { Empty } from './ui';

const ICONS: Record<string, { icon: typeof IconNote; color: string }> = {
  note: { icon: IconNote, color: 'yellow' },
  call: { icon: IconPhone, color: 'teal' },
  meeting: { icon: IconUsers, color: 'violet' },
  email_out: { icon: IconMail, color: 'blue' },
  email_in: { icon: IconMailOpened, color: 'cyan' },
  field_change: { icon: IconPencil, color: 'gray' },
  stage_change: { icon: IconArrowRight, color: 'indigo' },
  created: { icon: IconPlus, color: 'gray' },
  converted: { icon: IconTransform, color: 'teal' },
  proposal: { icon: IconFileText, color: 'orange' },
  invoice: { icon: IconFileInvoice, color: 'grape' },
  payment: { icon: IconCash, color: 'green' },
  file: { icon: IconFile, color: 'gray' },
  task_done: { icon: IconCheck, color: 'teal' },
  status_change: { icon: IconArrowRight, color: 'gray' },
};

const FILTERS = [
  { value: 'all', label: 'Все' },
  { value: 'comm', label: 'Общение' },
  { value: 'note', label: 'Заметки' },
  { value: 'system', label: 'Изменения' },
];
const FILTER_TYPES: Record<string, string[]> = {
  comm: ['call', 'meeting', 'email_out', 'email_in'],
  note: ['note'],
  system: ['field_change', 'stage_change', 'created', 'converted', 'status_change', 'file', 'proposal', 'invoice', 'payment'],
};

function ChangeList({ changes }: { changes: Record<string, [unknown, unknown]> }) {
  return (
    <Stack gap={2} mt={4}>
      {Object.entries(changes).map(([k, [a, b]]) => (
        <Text size="xs" c="dimmed" key={k}>
          {FIELD_LABELS[k] ?? k}: <s>{String(a ?? '—')}</s> → <b>{String(b ?? '—')}</b>
        </Text>
      ))}
    </Stack>
  );
}

export default function Timeline({ filter, compact }: {
  filter: { company_id?: number; contact_id?: number; deal_id?: number; lead_id?: number }; compact?: boolean;
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [kind, setKind] = useState('all');
  const [limit, setLimit] = useState(20);
  const [noteType, setNoteType] = useState<'note' | 'call' | 'meeting'>('note');
  const [text, setText] = useState('');
  const [saving, setSaving] = useState(false);
  const { data, isLoading } = useApi<Page<Activity>>(['activities'], '/activities', {
    ...filter, type: kind === 'all' ? undefined : FILTER_TYPES[kind], page_size: limit,
  });

  const add = async () => {
    if (!text.trim()) return;
    setSaving(true);
    try {
      await api.post('/activities', { type: noteType, body: text, ...filter });
      setText('');
      qc.invalidateQueries({ queryKey: ['activities'] });
      qc.invalidateQueries({ queryKey: ['company'] });
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };

  const remove = async (id: number) => {
    await api.delete(`/activities/${id}`).catch(notifyError);
    qc.invalidateQueries({ queryKey: ['activities'] });
  };

  return (
    <Stack>
      {!compact && (
        <Box>
          <SegmentedControl size="xs" mb="xs" value={noteType} onChange={(v) => setNoteType(v as typeof noteType)}
            data={[{ value: 'note', label: 'Заметка' }, { value: 'call', label: 'Звонок' }, { value: 'meeting', label: 'Встреча' }]} />
          <Textarea placeholder={noteType === 'note' ? 'Добавить заметку…' : 'Итог разговора / встречи…'}
            autosize minRows={2} value={text} onChange={(e) => setText(e.currentTarget.value)}
            onKeyDown={(e) => {
              if (e.key === 'Enter' && (e.ctrlKey || e.metaKey)) add();
            }} />
          <Group justify="space-between" mt="xs">
            <Text size="xs" c="dimmed">
              Ctrl+Enter — сохранить
            </Text>
            <Button size="xs" onClick={add} loading={saving} disabled={!text.trim()}>
              Сохранить
            </Button>
          </Group>
        </Box>
      )}
      <SegmentedControl size="xs" data={FILTERS} value={kind} onChange={setKind} />
      {isLoading ? (
        <Loader size="sm" />
      ) : !data?.items.length ? (
        <Empty text="Событий пока нет" />
      ) : (
        <MTimeline bulletSize={28} lineWidth={2}>
          {data.items.map((a) => {
            const conf = ICONS[a.type] ?? { icon: IconNote, color: 'gray' };
            const Icon = a.type === 'call' && a.meta?.direction === 'in' ? IconPhoneIncoming : conf.icon;
            return (
              <MTimeline.Item key={a.id} bullet={<ThemeIcon size={28} radius="xl" color={conf.color} variant="light">
                <Icon size={15} />
              </ThemeIcon>}>
                <Group justify="space-between" gap="xs" wrap="nowrap" align="flex-start">
                  <Text size="sm" fw={500} style={{ wordBreak: 'break-word' }}>
                    {a.title}
                  </Text>
                  {a.type === 'note' && (a.user?.id === user?.id || user?.role === 'admin' || user?.role === 'head') && (
                    <Tooltip label="Удалить">
                      <ActionIcon size="sm" variant="subtle" color="gray" onClick={() => remove(a.id)} aria-label="Удалить">
                        <IconTrash size={14} />
                      </ActionIcon>
                    </Tooltip>
                  )}
                </Group>
                {a.body && (
                  <Text size="sm" c="dimmed" className="timeline-body" mt={2} lineClamp={compact ? 3 : undefined}>
                    {a.body}
                  </Text>
                )}
                {a.meta?.changes && <ChangeList changes={a.meta.changes} />}
                {a.type === 'call' && (a.meta?.duration || a.meta?.recording_url) && (
                  <Group gap="xs" mt={4}>
                    {a.meta.duration ? <Badge size="xs" variant="outline">{Math.round(a.meta.duration / 60)} мин</Badge> : null}
                    {a.meta.missed && <Badge size="xs" color="red">Пропущен</Badge>}
                    {a.meta.recording_url && (
                      <Anchor size="xs" href={a.meta.recording_url} target="_blank">
                        Запись разговора
                      </Anchor>
                    )}
                  </Group>
                )}
                <Text size="xs" c="dimmed" mt={4}>
                  <Tooltip label={dateTime(a.occurred_at)}>
                    <span>{smartDate(a.occurred_at)}</span>
                  </Tooltip>
                  {a.user ? ` · ${a.user.full_name}` : ' · Система'}
                </Text>
              </MTimeline.Item>
            );
          })}
        </MTimeline>
      )}
      {data && data.total > data.items.length && (
        <Button variant="subtle" size="xs" onClick={() => setLimit((l) => l + 30)}>
          Показать ещё ({data.total - data.items.length})
        </Button>
      )}
    </Stack>
  );
}
