import { useListState } from '@/lib/useListState';
import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Button, Group, Modal, MultiSelect, Paper, Select, Stack, Table, Text, TextInput } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { IconPlus, IconSearch } from '@tabler/icons-react';
import { api, notifyError } from '@/api/client';
import { useApi, useTemplates } from '@/api/hooks';
import type { Page, Proposal } from '@/api/types';
import { CompanySelect } from '@/components/selects';
import { Empty, PageHeader, Pager, StatusBadge } from '@/components/ui';
import { date, dateTime, money } from '@/lib/format';
import { PROPOSAL_STATUS } from '@/lib/labels';

function NewProposalModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const { data: templates } = useTemplates();
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [templateId, setTemplateId] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const create = async () => {
    setSaving(true);
    try {
      const { data } = await api.post('/proposals', { company_id: companyId, template_id: templateId ? Number(templateId) : null });
      navigate(`/proposals/${data.id}`);
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal opened={opened} onClose={onClose} title="Новое коммерческое предложение">
      <Stack>
        <CompanySelect label="Клиент" value={companyId} onChange={setCompanyId} withAsterisk />
        <Select label="Шаблон" data={(templates ?? []).filter((t) => t.is_active).map((t) => ({ value: String(t.id), label: t.name }))}
          value={templateId} onChange={setTemplateId} clearable placeholder="Без шаблона" />
        <Text size="xs" c="dimmed">Удобнее создавать КП из карточки сделки — позиции подтянутся автоматически.</Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button onClick={create} loading={saving} disabled={!companyId}>Создать</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function ProposalsPage() {
  const navigate = useNavigate();
  const [q, setQ] = useListState('q', '');
  const [debounced] = useDebouncedValue(q, 300);
  const [status, setStatus] = useListState<string[]>('status', []);
  const [page, setPage] = useListState('page', 1);
  const [creating, setCreating] = useState(false);
  const { data, isLoading } = useApi<Page<Proposal>>(['proposals'], '/proposals', {
    q: debounced || undefined, status, page, page_size: 25,
  });
  return (
    <>
      <PageHeader title="Коммерческие предложения" subtitle="Конструктор КП, отправка клиенту и отслеживание просмотров"
        actions={<Button leftSection={<IconPlus size={16} />} onClick={() => setCreating(true)}>КП</Button>} />
      <Paper withBorder p="md" mb="md">
        <Group>
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Номер, название, клиент" w={300} value={q}
            onChange={(e) => { setQ(e.currentTarget.value); setPage(1); }} aria-label="Поиск" />
          <MultiSelect placeholder="Статус" w={320} clearable value={status} onChange={(v) => { setStatus(v); setPage(1); }}
            data={Object.entries(PROPOSAL_STATUS).map(([value, s]) => ({ value, label: s.label }))} aria-label="Статус" />
        </Group>
      </Paper>
      <Paper withBorder>
        <Table.ScrollContainer minWidth={900}>
          <Table>
            <Table.Thead>
              <Table.Tr>
                <Table.Th>Номер</Table.Th><Table.Th>Клиент</Table.Th><Table.Th ta="right">Сумма</Table.Th>
                <Table.Th>Статус</Table.Th><Table.Th>Отправлено</Table.Th><Table.Th>Просмотрено</Table.Th><Table.Th>Менеджер</Table.Th>
              </Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.items.map((p) => (
                <Table.Tr key={p.id} className="clickable-row" onClick={() => navigate(`/proposals/${p.id}`)}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{p.number}</Text>
                    <Text size="xs" c="dimmed">{date(p.created_at)}</Text>
                  </Table.Td>
                  <Table.Td><Text size="sm">{p.company?.name ?? '—'}</Text></Table.Td>
                  <Table.Td ta="right">{money(p.total, p.currency)}</Table.Td>
                  <Table.Td><StatusBadge map={PROPOSAL_STATUS} value={p.status} /></Table.Td>
                  <Table.Td><Text size="sm">{p.sent_at ? dateTime(p.sent_at) : '—'}</Text></Table.Td>
                  <Table.Td><Text size="sm" c={p.viewed_at ? 'teal' : 'dimmed'}>{p.viewed_at ? dateTime(p.viewed_at) : '—'}</Text></Table.Td>
                  <Table.Td><Text size="sm">{p.owner?.full_name}</Text></Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
        {!isLoading && !data?.items.length && <Empty text="КП не найдены" />}
      </Paper>
      {data && <Pager page={page} pages={data.pages} total={data.total} pageSize={25} onPage={setPage} />}
      <NewProposalModal opened={creating} onClose={() => setCreating(false)} />
    </>
  );
}
