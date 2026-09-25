import { useListState } from '@/lib/useListState';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Button, Group, MultiSelect, Paper, Table, Text, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconPlus, IconSearch } from '@tabler/icons-react';
import { useApi } from '@/api/hooks';
import type { Contact, Page } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { ContactModal } from '@/components/forms';
import SortTh from '@/components/SortTh';
import { Empty, EntityLink, PageHeader, Pager, Phone } from '@/components/ui';
import { CONTACT_ROLES } from '@/lib/labels';

export default function ContactsPage() {
  const navigate = useNavigate();
  const { can } = useAuth();
  const [q, setQ] = useListState('q', '');
  const [debounced] = useDebouncedValue(q, 300);
  const [roles, setRoles] = useListState<string[]>('roles', []);
  const [sort, setSort] = useState('full_name');
  const [page, setPage] = useListState('page', 1);
  const [pageSize, setPageSize] = useState(25);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useApi<Page<Contact>>(['contacts'], '/contacts', {
    q: debounced || undefined, role_in_deal: roles, sort, page, page_size: pageSize,
  });

  return (
    <>
      <PageHeader title="Контакты" subtitle="Контактные лица клиентов"
        actions={can('companies.edit') && (
          <Button leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>
            Контакт
          </Button>
        )} />
      <Paper withBorder p="md" mb="md">
        <Group>
          <TextInput leftSection={<IconSearch size={16} />} placeholder="ФИО, email, телефон, должность" w={320}
            value={q} onChange={(e) => { setQ(e.currentTarget.value); setPage(1); }} aria-label="Поиск" />
          <MultiSelect placeholder="Роль в сделке" w={260} clearable value={roles} aria-label="Роль"
            onChange={(v) => { setRoles(v); setPage(1); }}
            data={Object.entries(CONTACT_ROLES).map(([value, label]) => ({ value, label }))} />
        </Group>
      </Paper>
      <Paper withBorder>
        <Table.ScrollContainer minWidth={800}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <SortTh field="full_name" sort={sort} onSort={setSort}>ФИО</SortTh>
                <Table.Th>Компания</Table.Th>
                <Table.Th>Роль</Table.Th>
                <Table.Th>Телефон</Table.Th>
                <Table.Th>Email</Table.Th>
                <Table.Th>Ответственный</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.items.map((c) => (
                <Table.Tr key={c.id} className="clickable-row" onClick={() => navigate(`/contacts/${c.id}`)}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{c.full_name}</Text>
                    <Text size="xs" c="dimmed">{c.position}</Text>
                  </Table.Td>
                  <Table.Td>{c.company ? <EntityLink to={`/companies/${c.company.id}`}>{c.company.name}</EntityLink> : '—'}</Table.Td>
                  <Table.Td>{c.role_in_deal && <Badge size="sm" variant="outline">{CONTACT_ROLES[c.role_in_deal]}</Badge>}</Table.Td>
                  <Table.Td onClick={(e) => e.stopPropagation()}>
                    <Phone phone={c.phone_mobile || c.phone_work} links={{ contact_id: c.id }} />
                  </Table.Td>
                  <Table.Td><Text size="sm">{c.email ?? '—'}</Text></Table.Td>
                  <Table.Td><Text size="sm">{c.owner?.full_name ?? '—'}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!isLoading && !data?.items.length && <Empty text="Контакты не найдены" />}
      </Paper>
      {data && (
        <Pager page={page} pages={data.pages} total={data.total} pageSize={pageSize} onPage={setPage}
          onPageSize={(s) => { setPageSize(s); setPage(1); }} />
      )}
      <ContactModal opened={creating} onClose={() => setCreating(false)} onSaved={(c) => navigate(`/contacts/${c.id}`)} />
    </>
  );
}
