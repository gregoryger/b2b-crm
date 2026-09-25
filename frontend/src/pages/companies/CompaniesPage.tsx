import { useListState } from '@/lib/useListState';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Button,
  Checkbox,
  Group,
  Menu,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  Table,
  Text,
  TextInput,
} from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconDownload, IconFilter, IconPlus, IconSearch, IconUpload, IconUserShare } from '@tabler/icons-react';
import { api, download, notifyError, notifyOk } from '@/api/client';
import { useApi, useDict, useUsers } from '@/api/hooks';
import type { Company, Page } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { useQuickCreate } from '@/components/QuickCreate';
import SortTh from '@/components/SortTh';
import { Empty, PageHeader, Pager, QueryFeedback, StatusBadge } from '@/components/ui';
import { ago, money } from '@/lib/format';
import { COMPANY_STATUS } from '@/lib/labels';
import ImportModal from './ImportModal';
import { useQueryClient } from '@tanstack/react-query';

export default function CompaniesPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const { open } = useQuickCreate();
  const qc = useQueryClient();
  const [q, setQ] = useListState('q', '');
  const [debounced] = useDebouncedValue(q, 300);
  const [industry, setIndustry] = useListState<string[]>('industry', []);
  const [region, setRegion] = useListState<string[]>('region', []);
  const [status, setStatus] = useListState<string[]>('status', []);
  const [manager, setManager] = useListState<string | null>('manager', null);
  const [revenueMin, setRevenueMin] = useListState<number | string>('revenueMin', '');
  const [noContact, setNoContact] = useListState<string | null>('noContact', null);
  const [sort, setSort] = useListState('sort', '-created_at');
  const [page, setPage] = useListState('page', 1);
  const [pageSize, setPageSize] = useListState('pageSize', 25);
  const [selected, setSelected] = useState<number[]>([]);
  const [importOpen, setImportOpen] = useState(false);
  const industries = useDict('industry');
  const regions = useDict('region');
  const users = useUsers('manager,head');

  const params = {
    q: debounced || undefined, industry_id: industry, region_id: region, status, manager_id: manager ?? undefined,
    revenue_min: revenueMin === '' ? undefined : revenueMin, no_contact_days: noContact ?? undefined,
  };
  const query = useApi<Page<Company>>(['companies'], '/companies', { ...params, sort, page, page_size: pageSize });
  const { data, isLoading, isError } = query;
  const setFilter = <T,>(fn: (v: T) => void) => (v: T) => {
    fn(v);
    setPage(1);
  };
  const allSelected = !!data?.items.length && data.items.every((c) => selected.includes(c.id));

  const bulkAssign = async (userId: string) => {
    try {
      const { data: r } = await api.post('/companies/bulk-assign', { ids: selected, user_id: Number(userId) });
      notifyOk(`Передано компаний: ${r.updated}`);
      setSelected([]);
      qc.invalidateQueries({ queryKey: ['companies'] });
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <>
      <PageHeader
        title="Компании"
        subtitle="База клиентов — юридических лиц"
        actions={
          <>
            {can('import') && (
              <Button variant="default" leftSection={<IconUpload size={16} />} onClick={() => setImportOpen(true)}>
                Импорт
              </Button>
            )}
            {can('export') && (
              <Button variant="default" leftSection={<IconDownload size={16} />}
                onClick={() => download('/export/companies', { ...params, format: 'xlsx' }, 'Клиенты.xlsx')}>
                Выгрузить сегмент
              </Button>
            )}
            {can('companies.edit') && (
              <Button leftSection={<IconPlus size={16} />} onClick={() => open('company')}>
                Компания
              </Button>
            )}
          </>
        }
      />
      <Paper withBorder p="md" mb="md">
        <Group gap="sm" align="flex-end">
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Название, ИНН, телефон, ФИО контакта"
            value={q} onChange={(e) => setFilter(setQ)(e.currentTarget.value)} w={300} aria-label="Поиск" />
          <MultiSelect placeholder="Отрасль" data={industries.options} value={industry} onChange={setFilter(setIndustry)}
            w={200} clearable searchable aria-label="Отрасль" />
          <MultiSelect placeholder="Регион" data={regions.options} value={region} onChange={setFilter(setRegion)}
            w={200} clearable searchable aria-label="Регион" />
          <MultiSelect placeholder="Статус" w={200} clearable aria-label="Статус" value={status}
            onChange={setFilter(setStatus)}
            data={Object.entries(COMPANY_STATUS).map(([value, v]) => ({ value, label: v.label }))} />
          {can('companies.view_all') && (
            <Select placeholder="Ответственный" data={users.options} value={manager} onChange={setFilter(setManager)}
              w={200} clearable searchable aria-label="Ответственный" />
          )}
          <NumberInput placeholder="Сумма покупок от, ₽" value={revenueMin} onChange={setFilter(setRevenueMin)} w={190}
            thousandSeparator=" " min={0} aria-label="Сумма покупок от" />
          <Select placeholder="Последний контакт" w={210} clearable value={noContact} onChange={setFilter(setNoContact)}
            leftSection={<IconFilter size={14} />} aria-label="Последний контакт"
            data={[{ value: '14', label: 'Нет контакта 14+ дней' }, { value: '30', label: 'Нет контакта 30+ дней' },
              { value: '90', label: 'Нет контакта 90+ дней' }]} />
        </Group>
      </Paper>

      {!!selected.length && can('companies.reassign') && (
        <Paper withBorder p="xs" mb="sm" bg="blue.0">
          <Group>
            <Text size="sm">Выбрано: {selected.length}</Text>
            <Menu>
              <Menu.Target>
                <Button size="xs" leftSection={<IconUserShare size={14} />}>
                  Передать менеджеру
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                {users.options.map((u) => (
                  <Menu.Item key={u.value} onClick={() => bulkAssign(u.value)}>
                    {u.label}
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
            <Button size="xs" variant="subtle" onClick={() => setSelected([])}>
              Снять выделение
            </Button>
          </Group>
        </Paper>
      )}

      <QueryFeedback query={query} hasData={!!data} />
      <Paper withBorder>
        <Table.ScrollContainer minWidth={900}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                {can('companies.reassign') && (
                  <Table.Th w={36}>
                    <Checkbox checked={allSelected} aria-label="Выбрать все"
                      onChange={() => setSelected(allSelected ? [] : data?.items.map((c) => c.id) ?? [])} />
                  </Table.Th>
                )}
                <SortTh field="name" sort={sort} onSort={setSort}>Компания</SortTh>
                <Table.Th>Отрасль / регион</Table.Th>
                <Table.Th>Статус</Table.Th>
                <Table.Th>Ответственный</Table.Th>
                <SortTh field="revenue" sort={sort} onSort={setSort} ta="right">Сумма покупок</SortTh>
                <Table.Th ta="right">Сделок в работе</Table.Th>
                <SortTh field="last_contact_at" sort={sort} onSort={setSort}>Последний контакт</SortTh>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.items.map((c) => (
                <Table.Tr key={c.id} className="clickable-row" onClick={() => navigate(`/companies/${c.id}`)}>
                  {can('companies.reassign') && (
                    <Table.Td onClick={(e) => e.stopPropagation()}>
                      <Checkbox checked={selected.includes(c.id)} aria-label={`Выбрать ${c.name}`}
                        onChange={() => setSelected(selected.includes(c.id) ? selected.filter((x) => x !== c.id) : [...selected, c.id])} />
                    </Table.Td>
                  )}
                  <Table.Td>
                    <Text size="sm" fw={500}>
                      {c.name}
                    </Text>
                    {c.inn && (
                      <Text size="xs" c="dimmed">
                        ИНН {c.inn}
                      </Text>
                    )}
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{c.industry?.name ?? '—'}</Text>
                    <Text size="xs" c="dimmed">
                      {c.region?.name}
                    </Text>
                  </Table.Td>
                  <Table.Td>
                    <StatusBadge map={COMPANY_STATUS} value={c.status} />
                  </Table.Td>
                  <Table.Td>
                    <Text size="sm">{c.manager?.full_name ?? '—'}</Text>
                  </Table.Td>
                  <Table.Td ta="right">{c.total_revenue ? money(c.total_revenue) : '—'}</Table.Td>
                  <Table.Td ta="right">{c.open_deals || '—'}</Table.Td>
                  <Table.Td>
                    <Text size="sm" c={!c.last_contact_at ? 'dimmed' : undefined}>
                      {c.last_contact_at ? ago(c.last_contact_at) : 'не было'}
                    </Text>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!isLoading && !isError && !data?.items.length && <Empty text="Компании не найдены" />}
      </Paper>
      {data && (
        <Pager page={page} pages={data.pages} total={data.total} pageSize={pageSize} onPage={setPage}
          onPageSize={(s) => { setPageSize(s); setPage(1); }} />
      )}
      <ImportModal opened={importOpen} onClose={() => setImportOpen(false)} />
    </>
  );
}
