import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ActionIcon,
  Alert,
  Anchor,
  Badge,
  Box,
  Button,
  Card,
  Center,
  Grid,
  Group,
  Loader,
  Menu,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
  Tooltip,
  UnstyledButton,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import {
  IconArrowLeft,
  IconCheck,
  IconDots,
  IconEdit,
  IconFileInvoice,
  IconFileText,
  IconMail,
  IconPlus,
  IconTrash,
  IconX,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi, useStages, useUsers } from '@/api/hooks';
import type { DealDetail, DealLine, Invoice, Page, Proposal } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { CustomFieldsView } from '@/components/CustomFields';
import EmailModal from '@/components/EmailModal';
import FilesPanel from '@/components/FilesPanel';
import { DealModal } from '@/components/forms';
import LinesEditor from '@/components/LinesEditor';
import { ContactSelect } from '@/components/selects';
import TasksPanel from '@/components/TasksPanel';
import Timeline from '@/components/Timeline';
import { Empty, EntityLink, Field, Phone, StatusBadge } from '@/components/ui';
import { date, dateTime, money } from '@/lib/format';
import { CONTACT_ROLES, INVOICE_STATUS, PROPOSAL_STATUS } from '@/lib/labels';
import LostModal from './LostModal';

function StageBar({ deal, onMove }: { deal: DealDetail; onMove: (stageId: number) => void }) {
  const { data: stages } = useStages();
  const open = (stages ?? []).filter((s) => s.is_active && s.kind === 'open');
  const idx = open.findIndex((s) => s.id === deal.stage.id);
  return (
    <Group gap={4} wrap="nowrap" style={{ overflowX: 'auto' }} pb={4}>
      {open.map((s, i) => {
        const passed = deal.status === 'won' || (deal.status === 'open' && i <= idx);
        return (
          <Tooltip key={s.id} label={`${s.name} · ${s.probability}%`}>
            <UnstyledButton onClick={() => onMove(s.id)} disabled={s.id === deal.stage.id}
              style={{
                flex: 1, minWidth: 110, padding: '8px 10px', textAlign: 'center', borderRadius: 6,
                background: passed ? `var(--mantine-color-${deal.status === 'won' ? 'teal' : 'blue'}-6)` : 'var(--mantine-color-gray-2)',
                color: passed ? 'white' : 'var(--mantine-color-gray-7)', fontSize: 13, fontWeight: 500,
                outline: s.id === deal.stage.id ? '2px solid var(--mantine-color-blue-9)' : undefined,
              }}>
              <Text size="xs" fw={600} truncate inherit>{s.name}</Text>
            </UnstyledButton>
          </Tooltip>
        );
      })}
    </Group>
  );
}

function Participants({ deal }: { deal: DealDetail }) {
  const qc = useQueryClient();
  const users = useUsers();
  const [contactId, setContactId] = useState<number | null>(null);
  const save = async (body: object) => {
    try {
      await api.patch(`/deals/${deal.id}`, body);
      qc.invalidateQueries({ queryKey: ['deal', deal.id] });
    } catch (e) {
      notifyError(e);
    }
  };
  const contacts = deal.contacts.map((c) => ({ contact_id: c.contact.id, role: c.role }));
  const members = deal.members.map((m) => ({ user_id: m.user.id, role: m.role }));
  return (
    <SimpleGrid cols={{ base: 1, md: 2 }}>
      <div>
        <Text fw={600} size="sm" mb="xs">Со стороны клиента</Text>
        <Stack gap={6}>
          {deal.contacts.map((c) => (
            <Group key={c.contact.id} justify="space-between" wrap="nowrap">
              <div style={{ minWidth: 0 }}>
                <EntityLink to={`/contacts/${c.contact.id}`}>{c.contact.full_name}</EntityLink>
                <Text size="xs" c="dimmed">{[c.contact.position, c.role && CONTACT_ROLES[c.role]].filter(Boolean).join(' · ')}</Text>
              </div>
              <ActionIcon variant="subtle" color="gray" aria-label="Убрать"
                onClick={() => save({ contacts: contacts.filter((x) => x.contact_id !== c.contact.id) })}>
                <IconX size={14} />
              </ActionIcon>
            </Group>
          ))}
          <Group gap="xs" wrap="nowrap">
            <ContactSelect size="xs" companyId={deal.company?.id} value={contactId} onChange={setContactId} style={{ flex: 1 }}
              aria-label="Добавить контакт" />
            <Button size="xs" variant="light" disabled={!contactId}
              onClick={() => { save({ contacts: [...contacts, { contact_id: contactId }] }); setContactId(null); }}>
              Добавить
            </Button>
          </Group>
        </Stack>
      </div>
      <div>
        <Text fw={600} size="sm" mb="xs">Со стороны исполнителя</Text>
        <Stack gap={6}>
          <Group justify="space-between">
            <Text size="sm">{deal.owner?.full_name}</Text>
            <Badge size="sm" variant="outline">Ответственный</Badge>
          </Group>
          {deal.members.map((m) => (
            <Group key={m.user.id} justify="space-between" wrap="nowrap">
              <Text size="sm">{m.user.full_name}{m.role && <Text span c="dimmed" size="xs"> · {m.role}</Text>}</Text>
              <ActionIcon variant="subtle" color="gray" aria-label="Убрать"
                onClick={() => save({ members: members.filter((x) => x.user_id !== m.user.id) })}>
                <IconX size={14} />
              </ActionIcon>
            </Group>
          ))}
          <Select size="xs" placeholder="Добавить сотрудника" data={users.options.filter((u) => Number(u.value) !== deal.owner?.id)}
            value={null} searchable aria-label="Добавить сотрудника"
            onChange={(v) => v && save({ members: [...members, { user_id: Number(v), role: 'Участник' }] })} />
        </Stack>
      </div>
    </SimpleGrid>
  );
}

export default function DealCard() {
  const { id } = useParams();
  const did = Number(id);
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = useAuth();
  const { data: stages } = useStages();
  const { data: deal, isLoading } = useApi<DealDetail>(['deal', did], `/deals/${did}`);
  const { data: history } = useApi<{ from: string | null; to: string; changed_at: string; days_in_prev: number | null }[]>(
    ['deal-history', did], `/deals/${did}/history`);
  const { data: proposals } = useApi<Page<Proposal>>(['proposals', { deal: did }], can('proposals.edit') ? '/proposals' : null, { deal_id: did });
  const { data: invoices } = useApi<Page<Invoice>>(['invoices', { deal: did }], can('finance.view') ? '/invoices' : null, { deal_id: did });
  const [edit, setEdit] = useState(false);
  const [lostOpen, setLostOpen] = useState(false);
  const [email, setEmail] = useState(false);
  const [lines, setLines] = useState<DealLine[]>([]);
  const [linesDirty, setLinesDirty] = useState(false);
  const [savingLines, setSavingLines] = useState(false);
  useEffect(() => {
    if (deal) {
      setLines(deal.products.map((p) => ({ ...p })));
      setLinesDirty(false);
    }
  }, [deal]);

  if (isLoading) return <Center h="50vh"><Loader /></Center>;
  if (!deal) return <Empty text="Сделка не найдена или нет доступа" action={<Button onClick={() => navigate('/deals')}>К сделкам</Button>} />;

  const refresh = () => ['deal', 'deals', 'board', 'activities', 'deal-history', 'dashboard', 'company'].forEach((k) =>
    qc.invalidateQueries({ queryKey: [k] }));
  const move = async (stageId: number, lostReasonId?: number, comment?: string) => {
    const stage = stages?.find((s) => s.id === stageId);
    if (stage?.kind === 'lost' && !lostReasonId) return setLostOpen(true);
    try {
      await api.post(`/deals/${deal.id}/move`, { stage_id: stageId, lost_reason_id: lostReasonId, lost_comment: comment });
      if (stage?.kind === 'won') notifyOk('Поздравляем с победой! 🎉', 'Сделка выиграна');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const won = stages?.find((s) => s.kind === 'won');
  const lost = stages?.find((s) => s.kind === 'lost');
  const reopenStage = stages?.filter((s) => s.kind === 'open').slice(-1)[0];

  const saveLines = async () => {
    setSavingLines(true);
    try {
      await api.patch(`/deals/${deal.id}`, { products: lines.filter((l) => l.name.trim()) });
      notifyOk('Состав сделки сохранён, сумма пересчитана');
      refresh();
    } catch (e) {
      notifyError(e);
    } finally {
      setSavingLines(false);
    }
  };

  const createProposal = async () => {
    try {
      const { data } = await api.post('/proposals', { deal_id: deal.id, template_id: 1 });
      navigate(`/proposals/${data.id}`);
    } catch (e) {
      notifyError(e);
    }
  };
  const createInvoice = async () => {
    try {
      await api.post('/invoices', { deal_id: deal.id });
      notifyOk('Счёт выставлен');
      qc.invalidateQueries({ queryKey: ['invoices'] });
      qc.invalidateQueries({ queryKey: ['activities'] });
    } catch (e) {
      notifyError(e);
    }
  };
  const remove = () => modals.openConfirmModal({
    title: 'Удалить сделку?', labels: { confirm: 'Удалить', cancel: 'Отмена' }, confirmProps: { color: 'red' },
    children: <Text size="sm">Сделка «{deal.title}» будет удалена. Действие фиксируется в журнале аудита.</Text>,
    onConfirm: async () => {
      try {
        await api.delete(`/deals/${deal.id}`);
        notifyOk('Сделка удалена');
        navigate('/deals');
      } catch (e) {
        notifyError(e);
      }
    },
  });

  return (
    <>
      <Anchor component={Link} to="/deals" size="sm" c="dimmed">
        <Group gap={4}><IconArrowLeft size={14} /> Сделки</Group>
      </Anchor>
      <Group justify="space-between" mt="xs" mb="sm" align="flex-start">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Group gap="sm">
            <Title order={2}>{deal.title}</Title>
            {deal.status === 'won' && <Badge color="teal" size="lg">Успех</Badge>}
            {deal.status === 'lost' && <Badge color="red" size="lg">Отказ</Badge>}
          </Group>
          <Group gap="lg" mt={6}>
            <Text fw={700} size="xl">{money(deal.amount, deal.currency)}</Text>
            <Text size="sm" c="dimmed">Вероятность {deal.probability}%</Text>
            {deal.company && <EntityLink to={`/companies/${deal.company.id}`}>{deal.company.name}</EntityLink>}
          </Group>
        </div>
        <Group gap="xs">
          {deal.status === 'open' && won && lost && can('deals.edit') && (
            <>
              <Button color="teal" leftSection={<IconCheck size={16} />} onClick={() => move(won.id)}>Выиграна</Button>
              <Button color="red" variant="light" leftSection={<IconX size={16} />} onClick={() => setLostOpen(true)}>Проиграна</Button>
            </>
          )}
          {deal.status !== 'open' && reopenStage && can('deals.edit') && (
            <Button variant="default" onClick={() => move(reopenStage.id)}>Вернуть в работу</Button>
          )}
          <Menu position="bottom-end">
            <Menu.Target>
              <Button variant="default" px="xs" aria-label="Ещё"><IconDots size={18} /></Button>
            </Menu.Target>
            <Menu.Dropdown>
              {can('deals.edit') && <Menu.Item leftSection={<IconEdit size={16} />} onClick={() => setEdit(true)}>Редактировать</Menu.Item>}
              <Menu.Item leftSection={<IconMail size={16} />} onClick={() => setEmail(true)}>Написать письмо</Menu.Item>
              {can('proposals.edit') && <Menu.Item leftSection={<IconFileText size={16} />} onClick={createProposal}>Создать КП</Menu.Item>}
              {can('finance.edit') && <Menu.Item leftSection={<IconFileInvoice size={16} />} onClick={createInvoice}>Выставить счёт</Menu.Item>}
              {can('deals.delete') && (
                <>
                  <Menu.Divider />
                  <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={remove}>Удалить</Menu.Item>
                </>
              )}
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
      {deal.status !== 'lost' && <Box mb="md"><StageBar deal={deal} onMove={(s) => move(s)} /></Box>}
      {deal.status === 'lost' && (
        <Alert color="red" mb="md">Причина проигрыша: {deal.lost_reason?.name ?? '—'}{deal.lost_comment ? ` — ${deal.lost_comment}` : ''}</Alert>
      )}

      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Card p={0}>
            <Tabs defaultValue="info" keepMounted={false}>
              <Tabs.List px="md" pt="xs">
                <Tabs.Tab value="info">Инфо</Tabs.Tab>
                <Tabs.Tab value="products" rightSection={<Badge size="xs" variant="light">{deal.products.length}</Badge>}>Товары и услуги</Tabs.Tab>
                <Tabs.Tab value="docs">Документы</Tabs.Tab>
                <Tabs.Tab value="history">История этапов</Tabs.Tab>
              </Tabs.List>
              <Tabs.Panel value="info" p="lg">
                <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} mb="lg">
                  <Field label="Этап">{deal.stage.name}</Field>
                  <Field label="Плановая дата закрытия">{date(deal.close_date)}</Field>
                  <Field label="Ответственный">{deal.owner?.full_name}</Field>
                  <Field label="Контактное лицо">
                    {deal.contact && <EntityLink to={`/contacts/${deal.contact.id}`}>{deal.contact.full_name}</EntityLink>}
                  </Field>
                  <Field label="Телефон"><Phone phone={deal.contact?.phone_mobile} links={{ deal_id: deal.id, contact_id: deal.contact?.id }} /></Field>
                  <Field label="Email">{deal.contact?.email}</Field>
                  <Field label="Создана">{dateTime(deal.created_at)}</Field>
                  {deal.closed_at && <Field label="Закрыта">{dateTime(deal.closed_at)}</Field>}
                  {deal.lead_id && <Field label="Источник"><EntityLink to={`/leads/${deal.lead_id}`}>Лид #{deal.lead_id}</EntityLink></Field>}
                  <CustomFieldsView entity="deal" value={deal.custom_fields} />
                </SimpleGrid>
                {deal.description && <Text size="sm" mb="lg" style={{ whiteSpace: 'pre-wrap' }}>{deal.description}</Text>}
                <Title order={5} mb="sm">Участники сделки</Title>
                <Participants deal={deal} />
              </Tabs.Panel>
              <Tabs.Panel value="products" p="lg">
                <LinesEditor lines={lines} currency={deal.currency} vatRate={20} readOnly={!can('deals.edit')}
                  onChange={(l) => { setLines(l); setLinesDirty(true); }} />
                {linesDirty && (
                  <Group justify="flex-end" mt="md">
                    <Button variant="default" onClick={() => { setLines(deal.products); setLinesDirty(false); }}>Отменить</Button>
                    <Button onClick={saveLines} loading={savingLines}>Сохранить и пересчитать сумму</Button>
                  </Group>
                )}
              </Tabs.Panel>
              <Tabs.Panel value="docs" p="lg">
                <Stack>
                  {can('proposals.edit') && (
                    <div>
                      <Group justify="space-between" mb="xs">
                        <Title order={5}>Коммерческие предложения</Title>
                        <Button size="xs" variant="light" leftSection={<IconPlus size={14} />} onClick={createProposal}>КП</Button>
                      </Group>
                      {!proposals?.items.length ? <Text size="sm" c="dimmed">Нет КП</Text> : (
                        <Table>
                          <Table.Tbody>
                            {proposals.items.map((p) => (
                              <Table.Tr key={p.id} className="clickable-row" onClick={() => navigate(`/proposals/${p.id}`)}>
                                <Table.Td>{p.number}</Table.Td>
                                <Table.Td ta="right">{money(p.total, p.currency)}</Table.Td>
                                <Table.Td><StatusBadge map={PROPOSAL_STATUS} value={p.status} /></Table.Td>
                                <Table.Td><Text size="xs" c="dimmed">{p.viewed_at ? `открыто ${dateTime(p.viewed_at)}` : p.sent_at ? `отправлено ${date(p.sent_at)}` : ''}</Text></Table.Td>
                              </Table.Tr>
                            ))}
                          </Table.Tbody>
                        </Table>
                      )}
                    </div>
                  )}
                  {can('finance.view') && (
                    <div>
                      <Group justify="space-between" mb="xs">
                        <Title order={5}>Счета</Title>
                        {can('finance.edit') && <Button size="xs" variant="light" leftSection={<IconPlus size={14} />} onClick={createInvoice}>Счёт</Button>}
                      </Group>
                      {!invoices?.items.length ? <Text size="sm" c="dimmed">Нет счетов</Text> : (
                        <Table>
                          <Table.Tbody>
                            {invoices.items.map((i) => (
                              <Table.Tr key={i.id} className="clickable-row" onClick={() => navigate(`/finance?invoice=${i.id}`)}>
                                <Table.Td>{i.number}</Table.Td>
                                <Table.Td ta="right">{money(i.amount, i.currency)}</Table.Td>
                                <Table.Td><StatusBadge map={INVOICE_STATUS} value={i.status} />{i.is_overdue && <Badge color="red" ml={4} size="sm">Просрочен</Badge>}</Table.Td>
                                <Table.Td><Text size="xs" c="dimmed">оплатить до {date(i.due_date)}</Text></Table.Td>
                              </Table.Tr>
                            ))}
                          </Table.Tbody>
                        </Table>
                      )}
                    </div>
                  )}
                  <div>
                    <Title order={5} mb="xs">Файлы</Title>
                    <FilesPanel dealId={deal.id} />
                  </div>
                </Stack>
              </Tabs.Panel>
              <Tabs.Panel value="history" p="lg">
                <Table>
                  <Table.Thead>
                    <Table.Tr><Table.Th>Дата</Table.Th><Table.Th>Переход</Table.Th><Table.Th ta="right">На предыдущем этапе</Table.Th></Table.Tr>
                  </Table.Thead>
                  <Table.Tbody>
                    {history?.map((h, i) => (
                      <Table.Tr key={i}>
                        <Table.Td>{dateTime(h.changed_at)}</Table.Td>
                        <Table.Td>{h.from ? `${h.from} → ${h.to}` : `Создана на этапе «${h.to}»`}</Table.Td>
                        <Table.Td ta="right">{h.days_in_prev !== null ? `${h.days_in_prev} дн.` : '—'}</Table.Td>
                      </Table.Tr>
                    ))}
                  </Table.Tbody>
                </Table>
              </Tabs.Panel>
            </Tabs>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card>
              <Title order={5} mb="xs">Задачи</Title>
              <TasksPanel defaults={{ deal_id: deal.id, company_id: deal.company?.id, contact_id: deal.contact?.id }} />
            </Card>
            <Card>
              <Title order={5} mb="sm">Лента событий</Title>
              <Timeline filter={{ deal_id: deal.id }} />
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      <DealModal opened={edit} onClose={() => setEdit(false)} deal={deal} />
      <LostModal opened={lostOpen} onClose={() => setLostOpen(false)} onConfirm={(r, c) => {
        setLostOpen(false);
        if (lost) move(lost.id, r, c);
      }} />
      <EmailModal opened={email} onClose={() => setEmail(false)} to={deal.contact?.email}
        links={{ deal_id: deal.id, company_id: deal.company?.id, contact_id: deal.contact?.id }} />
    </>
  );
}
