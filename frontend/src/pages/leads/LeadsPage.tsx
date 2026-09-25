import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Button, Checkbox, Group, Menu, MultiSelect, Paper, Select, Table, Tabs, Text, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconPlus, IconSearch, IconUserShare } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi, useDict, useUsers } from '@/api/hooks';
import type { Lead, Page } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { useQuickCreate } from '@/components/QuickCreate';
import SortTh from '@/components/SortTh';
import { Empty, PageHeader, Pager, StatusBadge } from '@/components/ui';
import { dateTime, money, smartDate } from '@/lib/format';
import { LEAD_STATUS } from '@/lib/labels';

const TABS = [
  { value: 'active', label: 'В работе', statuses: ['new', 'in_progress'] },
  { value: 'new', label: 'Новые', statuses: ['new'] },
  { value: 'qualified', label: 'Квалифицированы', statuses: ['qualified'] },
  { value: 'rejected', label: 'Отклонены', statuses: ['rejected'] },
  { value: 'all', label: 'Все', statuses: [] as string[] },
];

export default function LeadsPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { open } = useQuickCreate();
  const qc = useQueryClient();
  const [tab, setTab] = useState('active');
  const [q, setQ] = useState('');
  const [debounced] = useDebouncedValue(q, 300);
  const [sources, setSources] = useState<string[]>([]);
  const [assignee, setAssignee] = useState<string | null>(null);
  const [sort, setSort] = useState('-created_at');
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(25);
  const [selected, setSelected] = useState<number[]>([]);
  const src = useDict('lead_source');
  const users = useUsers('manager,head');
  const { data: stats } = useApi<Record<string, number>>(['lead-stats'], '/leads/stats');
  const statuses = TABS.find((t) => t.value === tab)!.statuses;
  const { data, isLoading } = useApi<Page<Lead>>(['leads'], '/leads', {
    q: debounced || undefined, status: statuses, source_id: sources, assigned_to: assignee ?? undefined, sort, page,
    page_size: pageSize,
  });
  const count = (st: string[]) => (st.length ? st : Object.keys(stats ?? {})).reduce((s, k) => s + (stats?.[k] ?? 0), 0);
  const allSelected = !!data?.items.length && data.items.every((l) => selected.includes(l.id));

  const bulkAssign = async (userId: string) => {
    try {
      const { data: r } = await api.post('/leads/bulk-assign', { ids: selected, user_id: Number(userId) });
      notifyOk(`Назначено лидов: ${r.updated}`);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ['leads'] });
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <>
      <PageHeader title="Лиды" subtitle="Входящие заявки: сайт, почта, телефон, ручной ввод, API"
        actions={can('leads.edit') && <Button leftSection={<IconPlus size={16} />} onClick={() => open('lead')}>Лид</Button>} />
      <Tabs value={tab} onChange={(v) => { setTab(v!); setPage(1); setSelected([]); }} mb="md">
        <Tabs.List>
          {TABS.map((t) => (
            <Tabs.Tab key={t.value} value={t.value}
              rightSection={<Badge size="xs" variant={tab === t.value ? 'filled' : 'light'} color={t.value === 'new' ? 'blue' : 'gray'}>{count(t.statuses)}</Badge>}>
              {t.label}
            </Tabs.Tab>
          ))}
        </Tabs.List>
      </Tabs>
      <Paper withBorder p="md" mb="md">
        <Group>
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Запрос, компания, контакт, телефон, email" w={340}
            value={q} onChange={(e) => { setQ(e.currentTarget.value); setPage(1); }} aria-label="Поиск" />
          <MultiSelect placeholder="Источник" data={src.options} value={sources} w={240} clearable aria-label="Источник"
            onChange={(v) => { setSources(v); setPage(1); }} />
          {can('leads.view_all') && (
            <Select placeholder="Ответственный" data={users.options} value={assignee} w={220} clearable searchable
              aria-label="Ответственный" onChange={(v) => { setAssignee(v); setPage(1); }} />
          )}
        </Group>
      </Paper>
      {!!selected.length && can('leads.view_all') && (
        <Paper withBorder p="xs" mb="sm" bg="blue.0">
          <Group>
            <Text size="sm">Выбрано: {selected.length}</Text>
            <Menu>
              <Menu.Target>
                <Button size="xs" leftSection={<IconUserShare size={14} />}>Назначить ответственного</Button>
              </Menu.Target>
              <Menu.Dropdown>
                {users.options.map((u) => <Menu.Item key={u.value} onClick={() => bulkAssign(u.value)}>{u.label}</Menu.Item>)}
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Paper>
      )}
      <Paper withBorder>
        <Table.ScrollContainer minWidth={900}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                {can('leads.view_all') && (
                  <Table.Th w={36}>
                    <Checkbox checked={allSelected} aria-label="Выбрать все"
                      onChange={() => setSelected(allSelected ? [] : data?.items.map((l) => l.id) ?? [])} />
                  </Table.Th>
                )}
                <SortTh field="created_at" sort={sort} onSort={setSort}>Поступил</SortTh>
                <SortTh field="title" sort={sort} onSort={setSort}>Запрос</SortTh>
                <Table.Th>Клиент</Table.Th>
                <Table.Th>Источник</Table.Th>
                <SortTh field="status" sort={sort} onSort={setSort}>Статус</SortTh>
                <SortTh field="estimated_amount" sort={sort} onSort={setSort} ta="right">Бюджет</SortTh>
                <Table.Th>Ответственный</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.items.map((l) => (
                <Table.Tr key={l.id} className="clickable-row" onClick={() => navigate(`/leads/${l.id}`)}
                  fw={l.status === 'new' ? 600 : undefined}>
                  {can('leads.view_all') && (
                    <Table.Td onClick={(e) => e.stopPropagation()}>
                      <Checkbox checked={selected.includes(l.id)} aria-label="Выбрать"
                        onChange={() => setSelected(selected.includes(l.id) ? selected.filter((x) => x !== l.id) : [...selected, l.id])} />
                    </Table.Td>
                  )}
                  <Table.Td title={dateTime(l.created_at)}><Text size="sm">{smartDate(l.created_at)}</Text></Table.Td>
                  <Table.Td><Text size="sm" lineClamp={1}>{l.title}</Text></Table.Td>
                  <Table.Td>
                    <Text size="sm">{l.company_name ?? '—'}</Text>
                    <Text size="xs" c="dimmed">{[l.contact_name, l.phone].filter(Boolean).join(' · ')}</Text>
                  </Table.Td>
                  <Table.Td><Text size="sm">{l.source?.name ?? '—'}</Text></Table.Td>
                  <Table.Td><StatusBadge map={LEAD_STATUS} value={l.status} /></Table.Td>
                  <Table.Td ta="right">{l.estimated_amount ? money(l.estimated_amount) : '—'}</Table.Td>
                  <Table.Td><Text size="sm">{l.assignee?.full_name ?? <Text span c="orange" size="sm">не назначен</Text>}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!isLoading && !data?.items.length && <Empty text="Лидов нет" />}
      </Paper>
      {data && <Pager page={page} pages={data.pages} total={data.total} pageSize={pageSize} onPage={setPage}
        onPageSize={(s) => { setPageSize(s); setPage(1); }} />}
    </>
  );
}
