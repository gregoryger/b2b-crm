import { Fragment, useState } from 'react';
import { Badge, Card, Code, Group, MultiSelect, Select, Table, Text } from '@mantine/core';
import { useApi, useUsers } from '@/api/hooks';
import type { Page, UserRef } from '@/api/types';
import { Empty, Pager } from '@/components/ui';
import { dateTime } from '@/lib/format';
import { AUDIT_ACTIONS } from '@/lib/labels';
import { FIELD_LABELS } from '@/lib/fieldLabels';

interface AuditRow {
  id: number; user: UserRef | null; action: string; entity: string | null; entity_id: number | null; summary: string;
  changes: Record<string, [unknown, unknown]> | null; ip: string | null; created_at: string;
}
const DANGER = new Set(['delete', 'export', 'amount_change', 'login_failed', 'user_block', 'role_change', 'password_reset', 'import', 'export_1c']);

export default function AuditAdmin() {
  const users = useUsers();
  const [userId, setUserId] = useState<string | null>(null);
  const [actions, setActions] = useState<string[]>([]);
  const [days, setDays] = useState('30');
  const [page, setPage] = useState(1);
  const [open, setOpen] = useState<number | null>(null);
  const { data, isLoading } = useApi<Page<AuditRow>>(['audit'], '/audit', { user_id: userId ?? undefined, action: actions, days, page, page_size: 50 });
  return (
    <Card>
      <Group mb="md">
        <Select placeholder="Все сотрудники" data={users.options} value={userId} onChange={(v) => { setUserId(v); setPage(1); }} clearable searchable w={240} aria-label="Сотрудник" />
        <MultiSelect placeholder="Действия" w={360} clearable value={actions} onChange={(v) => { setActions(v); setPage(1); }} aria-label="Действия"
          data={Object.entries(AUDIT_ACTIONS).map(([value, label]) => ({ value, label }))} />
        <Select w={160} value={days} onChange={(v) => setDays(v!)} allowDeselect={false} aria-label="Период"
          data={[{ value: '1', label: 'За сутки' }, { value: '7', label: 'За неделю' }, { value: '30', label: 'За 30 дней' }, { value: '365', label: 'За год' }]} />
      </Group>
      <Table.ScrollContainer minWidth={800}>
        <Table>
          <Table.Thead><Table.Tr><Table.Th>Когда</Table.Th><Table.Th>Кто</Table.Th><Table.Th>Действие</Table.Th><Table.Th>Описание</Table.Th><Table.Th>IP</Table.Th></Table.Tr></Table.Thead>
          <Table.Tbody>
            {data?.items.map((r) => (
              <Fragment key={r.id}>
                <Table.Tr className={r.changes ? 'clickable-row' : undefined} onClick={() => setOpen(open === r.id ? null : r.id)}>
                  <Table.Td style={{ whiteSpace: 'nowrap' }}>{dateTime(r.created_at)}</Table.Td>
                  <Table.Td>{r.user?.full_name ?? '—'}</Table.Td>
                  <Table.Td><Badge color={DANGER.has(r.action) ? 'red' : 'gray'} variant="light">{AUDIT_ACTIONS[r.action] ?? r.action}</Badge></Table.Td>
                  <Table.Td><Text size="sm">{r.summary}{r.changes && <Text span c="blue" size="xs"> (изменения)</Text>}</Text></Table.Td>
                  <Table.Td><Text size="xs" c="dimmed">{r.ip}</Text></Table.Td>
                </Table.Tr>
                {open === r.id && r.changes && (
                  <Table.Tr>
                    <Table.Td colSpan={5}>
                      {Object.entries(r.changes).map(([k, [a, b]]) => (
                        <Text size="xs" key={k}>{FIELD_LABELS[k] ?? k}: <Code>{String(a ?? '—')}</Code> → <Code>{String(b ?? '—')}</Code></Text>
                      ))}
                    </Table.Td>
                  </Table.Tr>
                )}
              </Fragment>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {!isLoading && !data?.items.length && <Empty text="Записей нет" />}
      {data && <Pager page={page} pages={data.pages} total={data.total} pageSize={50} onPage={setPage} />}
    </Card>
  );
}
