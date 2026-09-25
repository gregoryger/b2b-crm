import { useEffect, useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ActionIcon,
  Badge,
  Button,
  Drawer,
  Group,
  Modal,
  MultiSelect,
  NumberInput,
  Paper,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Tabs,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useDebouncedValue } from '@mantine/hooks';
import { IconDownload, IconEye, IconFileExport, IconSearch, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, download, notifyError, notifyOk, openPdf } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Act, Invoice, Page, Report } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { Empty, EntityLink, PageHeader, Pager, StatCard, StatusBadge } from '@/components/ui';
import { date, dayjs, money, moneyShort, plural, toISODate } from '@/lib/format';
import { ACT_STATUS, INVOICE_STATUS } from '@/lib/labels';
import { IconAlertTriangle, IconCash, IconReceipt } from '@tabler/icons-react';

function InvoiceDrawer({ id, onClose }: { id: number | null; onClose: () => void }) {
  const qc = useQueryClient();
  const { can } = useAuth();
  const { data: inv } = useApi<Invoice>(['invoice', id], id ? `/invoices/${id}` : null);
  const [amount, setAmount] = useState<number | string>('');
  const [paidAt, setPaidAt] = useState<Date | null>(new Date());
  const [comment, setComment] = useState('');
  useEffect(() => {
    if (inv) setAmount(inv.debt);
  }, [inv]);
  const refresh = () => ['invoice', 'invoices', 'invoices-summary', 'acts', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
  const pay = async () => {
    try {
      await api.post(`/invoices/${id}/payments`, { amount: Number(amount), paid_at: toISODate(paidAt), comment: comment || null });
      notifyOk('Оплата зафиксирована');
      setComment('');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const act = async () => {
    try {
      await api.post('/acts', { invoice_id: id });
      notifyOk('Акт сформирован');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const cancel = async () => {
    try {
      await api.patch(`/invoices/${id}`, { status: 'canceled' });
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const delPayment = async (pid: number) => {
    try {
      await api.delete(`/invoices/${id}/payments/${pid}`);
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  return (
    <Drawer opened={!!id} onClose={onClose} position="right" size="lg" title={inv ? `Счёт ${inv.number}` : ''}>
      {inv && (
        <Stack>
          <Group>
            <StatusBadge map={INVOICE_STATUS} value={inv.status} size="lg" />
            {inv.is_overdue && <Badge color="red" size="lg">Просрочен на {dayjs().diff(inv.due_date, 'day')} дн.</Badge>}
          </Group>
          <SimpleGrid cols={2}>
            <div><Text size="xs" c="dimmed">Клиент</Text>{inv.company && <EntityLink to={`/companies/${inv.company.id}`}>{inv.company.name}</EntityLink>}</div>
            <div><Text size="xs" c="dimmed">Сделка</Text>{inv.deal_id ? <EntityLink to={`/deals/${inv.deal_id}`}>открыть</EntityLink> : '—'}</div>
            <div><Text size="xs" c="dimmed">Выставлен</Text><Text size="sm">{date(inv.issued_at)}</Text></div>
            <div><Text size="xs" c="dimmed">Оплатить до</Text><Text size="sm">{date(inv.due_date)}</Text></div>
            <div><Text size="xs" c="dimmed">Сумма</Text><Text fw={700}>{money(inv.amount, inv.currency, 2)}</Text></div>
            <div><Text size="xs" c="dimmed">Остаток долга</Text><Text fw={700} c={inv.debt > 0 ? 'red' : 'teal'}>{money(inv.debt, inv.currency, 2)}</Text></div>
          </SimpleGrid>
          <Group>
            <Button variant="default" leftSection={<IconEye size={16} />} onClick={() => openPdf(`/invoices/${inv.id}/pdf`)}>PDF</Button>
            <Button variant="default" leftSection={<IconDownload size={16} />}
              onClick={() => download(`/invoices/${inv.id}/pdf`, { download: true }, `${inv.number}.pdf`)}>Скачать</Button>
            {can('finance.edit') && inv.status !== 'canceled' && <Button variant="default" onClick={act}>Сформировать акт</Button>}
            {can('finance.edit') && inv.status === 'issued' && !inv.payments?.length && (
              <Button variant="subtle" color="red" onClick={cancel}>Отменить счёт</Button>
            )}
          </Group>
          <Title order={5}>Позиции</Title>
          <Table>
            <Table.Tbody>
              {inv.items.map((l, i) => (
                <Table.Tr key={i}>
                  <Table.Td>{l.name}</Table.Td>
                  <Table.Td ta="right">{l.quantity} {l.unit}</Table.Td>
                  <Table.Td ta="right">{money(l.total ?? 0, inv.currency, 2)}</Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
          <Title order={5}>Оплаты</Title>
          {!inv.payments?.length ? <Text size="sm" c="dimmed">Оплат ещё не было</Text> : (
            <Table>
              <Table.Tbody>
                {inv.payments.map((p) => (
                  <Table.Tr key={p.id}>
                    <Table.Td>{date(p.paid_at)}</Table.Td>
                    <Table.Td>{p.comment}</Table.Td>
                    <Table.Td ta="right">{money(p.amount, inv.currency, 2)}</Table.Td>
                    <Table.Td w={40}>
                      {can('finance.edit') && (
                        <ActionIcon variant="subtle" color="red" onClick={() => delPayment(p.id)} aria-label="Удалить оплату">
                          <IconTrash size={14} />
                        </ActionIcon>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          )}
          {can('finance.edit') && inv.debt > 0 && inv.status !== 'canceled' && (
            <Paper withBorder p="md">
              <Text fw={600} size="sm" mb="xs">Зафиксировать оплату</Text>
              <SimpleGrid cols={2}>
                <NumberInput label="Сумма" value={amount} onChange={setAmount} thousandSeparator=" " decimalScale={2} min={0} max={inv.debt} />
                <DatePickerInput label="Дата оплаты" value={paidAt} onChange={setPaidAt} valueFormat="DD.MM.YYYY" />
              </SimpleGrid>
              <TextInput label="Комментарий" mt="xs" value={comment} onChange={(e) => setComment(e.currentTarget.value)}
                placeholder="Например: п/п №123" />
              <Button mt="sm" onClick={pay} disabled={!amount}>Добавить оплату</Button>
            </Paper>
          )}
        </Stack>
      )}
    </Drawer>
  );
}

function ExportModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const [range, setRange] = useState<[Date | null, Date | null]>([dayjs().startOf('month').toDate(), new Date()]);
  const [onlyNew, setOnlyNew] = useState(true);
  return (
    <Modal opened={opened} onClose={onClose} title="Выгрузка в 1С: Бухгалтерию">
      <Stack>
        <Text size="sm" c="dimmed">XML-файл со счетами, актами и контрагентами для загрузки обработкой «Загрузка из CRM».</Text>
        <DatePickerInput type="range" label="Период" value={range} onChange={setRange} valueFormat="DD.MM.YYYY" />
        <Switch label="Только ещё не выгруженные документы" checked={onlyNew} onChange={(e) => setOnlyNew(e.currentTarget.checked)} />
        <Group justify="flex-end">
          <Button disabled={!range[0] || !range[1]} leftSection={<IconFileExport size={16} />} onClick={() => {
            download('/integrations/1c/export', { date_from: toISODate(range[0]), date_to: toISODate(range[1]), only_new: onlyNew }, 'crm_1c.xml');
            onClose();
          }}>Выгрузить</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function FinancePage() {
  const { can } = useAuth();
  const qc = useQueryClient();
  const [params, setParams] = useSearchParams();
  const [tab, setTab] = useState('invoices');
  const [q, setQ] = useState('');
  const [debounced] = useDebouncedValue(q, 300);
  const [status, setStatus] = useState<string[]>([]);
  const [overdue, setOverdue] = useState(false);
  const [page, setPage] = useState(1);
  const [openId, setOpenId] = useState<number | null>(null);
  const [exportOpen, setExportOpen] = useState(false);

  useEffect(() => {
    const inv = params.get('invoice');
    if (inv) {
      setOpenId(Number(inv));
      params.delete('invoice');
      setParams(params, { replace: true });
    }
  }, [params, setParams]);

  const { data: summary } = useApi<{ receivable: number; overdue: number; overdue_count: number; paid_this_month: number }>(
    ['invoices-summary'], '/invoices/summary');
  const invoices = useApi<Page<Invoice>>(['invoices'], tab === 'invoices' ? '/invoices' : null,
    { q: debounced || undefined, status, overdue: overdue || undefined, page, page_size: 25 });
  const acts = useApi<Page<Act>>(['acts'], tab === 'acts' ? '/acts' : null, { page, page_size: 25 });
  const receivables = useApi<Report>(['receivables'], tab === 'debt' ? '/analytics/reports/receivables' : null);

  const setActStatus = async (id: number, s: string) => {
    try {
      await api.patch(`/acts/${id}`, { status: s });
      qc.invalidateQueries({ queryKey: ['acts'] });
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <>
      <PageHeader title="Счета и оплаты" subtitle="Счета, акты, дебиторская задолженность"
        actions={can('finance.edit') && (
          <Button variant="default" leftSection={<IconFileExport size={16} />} onClick={() => setExportOpen(true)}>Выгрузка в 1С</Button>
        )} />
      <SimpleGrid cols={{ base: 1, sm: 3 }} mb="md">
        <StatCard label="Дебиторская задолженность" value={moneyShort(summary?.receivable)} icon={<IconReceipt size={20} />} />
        <StatCard label="Просрочено" value={moneyShort(summary?.overdue)} hint={`${summary?.overdue_count ?? 0} ${plural(summary?.overdue_count ?? 0, ['счёт', 'счёта', 'счетов'])}`}
          icon={<IconAlertTriangle size={20} />} color="red" />
        <StatCard label="Поступило в этом месяце" value={moneyShort(summary?.paid_this_month)} icon={<IconCash size={20} />} color="teal" />
      </SimpleGrid>
      <Tabs value={tab} onChange={(v) => { setTab(v!); setPage(1); }} mb="md">
        <Tabs.List>
          <Tabs.Tab value="invoices">Счета</Tabs.Tab>
          <Tabs.Tab value="acts">Акты</Tabs.Tab>
          <Tabs.Tab value="debt">Дебиторка по срокам</Tabs.Tab>
        </Tabs.List>
      </Tabs>

      {tab === 'invoices' && (
        <>
          <Paper withBorder p="md" mb="md">
            <Group>
              <TextInput leftSection={<IconSearch size={16} />} placeholder="Номер счёта или клиент" w={280} value={q}
                onChange={(e) => { setQ(e.currentTarget.value); setPage(1); }} aria-label="Поиск" />
              <MultiSelect placeholder="Статус" w={300} clearable value={status} onChange={(v) => { setStatus(v); setPage(1); }}
                data={Object.entries(INVOICE_STATUS).map(([value, s]) => ({ value, label: s.label }))} aria-label="Статус" />
              <Switch label="Только просроченные" checked={overdue} onChange={(e) => { setOverdue(e.currentTarget.checked); setPage(1); }} />
            </Group>
          </Paper>
          <Paper withBorder>
            <Table.ScrollContainer minWidth={900}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <Table.Th>Счёт</Table.Th><Table.Th>Клиент</Table.Th><Table.Th ta="right">Сумма</Table.Th>
                    <Table.Th ta="right">Долг</Table.Th><Table.Th>Срок оплаты</Table.Th><Table.Th>Статус</Table.Th><Table.Th>Менеджер</Table.Th>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {invoices.data?.items.map((i) => (
                    <Table.Tr key={i.id} className="clickable-row" onClick={() => setOpenId(i.id)}>
                      <Table.Td><Text size="sm" fw={500}>{i.number}</Text><Text size="xs" c="dimmed">{date(i.issued_at)}</Text></Table.Td>
                      <Table.Td><Text size="sm">{i.company?.name}</Text></Table.Td>
                      <Table.Td ta="right">{money(i.amount, i.currency)}</Table.Td>
                      <Table.Td ta="right"><Text size="sm" c={i.debt > 0 ? (i.is_overdue ? 'red' : undefined) : 'dimmed'}>{i.debt > 0 ? money(i.debt, i.currency) : '—'}</Text></Table.Td>
                      <Table.Td><Text size="sm" c={i.is_overdue ? 'red' : undefined}>{date(i.due_date)}</Text></Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          <StatusBadge map={INVOICE_STATUS} value={i.status} />
                          {i.is_overdue && <Badge color="red" size="sm">Просрочен</Badge>}
                          {i.exported_1c_at && <Badge color="gray" variant="outline" size="sm">1С</Badge>}
                        </Group>
                      </Table.Td>
                      <Table.Td><Text size="sm">{i.owner?.full_name}</Text></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {!invoices.isLoading && !invoices.data?.items.length && <Empty text="Счетов нет" />}
          </Paper>
          {invoices.data && <Pager page={page} pages={invoices.data.pages} total={invoices.data.total} pageSize={25} onPage={setPage} />}
        </>
      )}

      {tab === 'acts' && (
        <>
          <Paper withBorder>
            <Table.ScrollContainer minWidth={800}>
              <Table>
                <Table.Thead>
                  <Table.Tr><Table.Th>Акт</Table.Th><Table.Th>Клиент</Table.Th><Table.Th ta="right">Сумма</Table.Th><Table.Th>Статус</Table.Th><Table.Th /></Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {acts.data?.items.map((a) => (
                    <Table.Tr key={a.id}>
                      <Table.Td><Text size="sm" fw={500}>{a.number}</Text><Text size="xs" c="dimmed">{date(a.act_date)}</Text></Table.Td>
                      <Table.Td>{a.company?.name}</Table.Td>
                      <Table.Td ta="right">{money(a.amount)}</Table.Td>
                      <Table.Td>
                        <Select size="xs" w={140} value={a.status} allowDeselect={false} disabled={!can('finance.edit')}
                          data={Object.entries(ACT_STATUS).map(([value, s]) => ({ value, label: s.label }))}
                          onChange={(v) => v && setActStatus(a.id, v)} aria-label="Статус акта" />
                      </Table.Td>
                      <Table.Td>
                        <Group gap={4}>
                          <ActionIcon variant="subtle" onClick={() => openPdf(`/acts/${a.id}/pdf`)} aria-label="Открыть PDF"><IconEye size={16} /></ActionIcon>
                          <ActionIcon variant="subtle" onClick={() => download(`/acts/${a.id}/pdf`, { download: true }, `${a.number}.pdf`)} aria-label="Скачать"><IconDownload size={16} /></ActionIcon>
                        </Group>
                      </Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {!acts.isLoading && !acts.data?.items.length && <Empty text="Актов нет" />}
          </Paper>
          {acts.data && <Pager page={page} pages={acts.data.pages} total={acts.data.total} pageSize={25} onPage={setPage} />}
        </>
      )}

      {tab === 'debt' && receivables.data && (
        <Stack>
          <SimpleGrid cols={{ base: 2, md: 5 }}>
            {[['current', 'Не просрочено', 'teal'], ['1_30', '1–30 дней', 'yellow'], ['31_60', '31–60 дней', 'orange'],
              ['61_90', '61–90 дней', 'red'], ['90_plus', 'Более 90 дней', 'red']].map(([k, label, color]) => (
              <Paper withBorder p="md" key={k} style={{ borderTop: `3px solid var(--mantine-color-${color}-6)` }}>
                <Text size="xs" c="dimmed">{label}</Text>
                <Text fw={700} size="lg">{moneyShort(receivables.data!.aging?.[k])}</Text>
              </Paper>
            ))}
          </SimpleGrid>
          <Paper withBorder>
            <Table.ScrollContainer minWidth={800}>
              <Table>
                <Table.Thead>
                  <Table.Tr><Table.Th>Счёт</Table.Th><Table.Th>Клиент</Table.Th><Table.Th>Менеджер</Table.Th><Table.Th>Срок</Table.Th>
                    <Table.Th ta="right">Долг</Table.Th><Table.Th ta="right">Просрочка</Table.Th></Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {receivables.data.rows.map((r) => (
                    <Table.Tr key={r.invoice_id} className="clickable-row" onClick={() => setOpenId(r.invoice_id)}>
                      <Table.Td>{r.invoice}</Table.Td><Table.Td>{r.company}</Table.Td><Table.Td>{r.manager}</Table.Td>
                      <Table.Td>{date(r.due_date)}</Table.Td><Table.Td ta="right">{money(r.debt)}</Table.Td>
                      <Table.Td ta="right"><Text size="sm" c={r.overdue_days ? 'red' : 'dimmed'}>{r.overdue_days ? `${r.overdue_days} дн.` : '—'}</Text></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {!receivables.data.rows.length && <Empty text="Задолженности нет" />}
          </Paper>
        </Stack>
      )}
      <InvoiceDrawer id={openId} onClose={() => setOpenId(null)} />
      <ExportModal opened={exportOpen} onClose={() => setExportOpen(false)} />
    </>
  );
}
