import { useCallback, useEffect, useRef, useState } from 'react';
import { Link, useBeforeUnload, useBlocker, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  CopyButton,
  Grid,
  Group,
  Loader,
  Menu,
  Modal,
  Popover,
  Select,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Timeline,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import {
  IconArrowLeft,
  IconBraces,
  IconCheck,
  IconCopy,
  IconDots,
  IconDownload,
  IconEye,
  IconFileInvoice,
  IconLink,
  IconSend,
  IconTrash,
  IconX,
} from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { modals } from '@mantine/modals';
import { api, download, notifyError, notifyOk, openPdf } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { DealLine, ProposalDetail } from '@/api/types';
import LinesEditor from '@/components/LinesEditor';
import { ContactSelect } from '@/components/selects';
import { Empty, EntityLink, QueryFeedback, StatusBadge } from '@/components/ui';
import { dateTime, toISODate } from '@/lib/format';
import { CURRENCIES, PROPOSAL_STATUS } from '@/lib/labels';

function VariablesHelp({ onInsert }: { onInsert: (v: string) => void }) {
  const { data } = useApi<{ key: string; label: string }[]>(['kp-vars'], '/proposal-templates/variables');
  return (
    <Popover width={320} position="bottom-end" shadow="md">
      <Popover.Target>
        <Button size="compact-xs" variant="subtle" leftSection={<IconBraces size={14} />}>Переменные</Button>
      </Popover.Target>
      <Popover.Dropdown>
        <Text size="xs" c="dimmed" mb="xs">Подставляются автоматически при формировании PDF. Нажмите, чтобы вставить:</Text>
        <Stack gap={2}>
          {data?.map((v) => (
            <Anchor key={v.key} size="xs" onClick={() => onInsert(v.key)}>
              <code>{v.key}</code> — {v.label}
            </Anchor>
          ))}
        </Stack>
      </Popover.Dropdown>
    </Popover>
  );
}

export default function ProposalEditor() {
  const { id } = useParams();
  const navigate = useNavigate();
  const qc = useQueryClient();
  const query = useApi<ProposalDetail>(['proposal', Number(id)], `/proposals/${id}`);
  const { data: p, isLoading } = query;
  const [form, setForm] = useState<Partial<ProposalDetail>>({});
  const [lines, setLines] = useState<DealLine[]>([]);
  const [dirty, setDirtyState] = useState(false);
  const dirtyRef = useRef(false);
  const loadedId = useRef<number>();
  const busyRef = useRef(false);
  const setDirty = (value: boolean) => { dirtyRef.current = value; setDirtyState(value); };
  const [saving, setSaving] = useState(false);
  const [sendOpen, setSendOpen] = useState(false);
  const [sendTo, setSendTo] = useState('');
  const [sendMsg, setSendMsg] = useState('');
  const [sending, setSending] = useState(false);
  const [acting, setActing] = useState(false);
  const blocker = useBlocker(({ currentLocation, nextLocation }) => dirtyRef.current && (
    currentLocation.pathname !== nextLocation.pathname || currentLocation.search !== nextLocation.search
  ));
  useBeforeUnload(useCallback((event: BeforeUnloadEvent) => {
    if (dirtyRef.current) { event.preventDefault(); event.returnValue = ''; }
  }, []));

  useEffect(() => {
    if (p) {
      if (dirtyRef.current && loadedId.current === p.id) return;
      loadedId.current = p.id;
      setForm({ title: p.title, intro_text: p.intro_text, terms_text: p.terms_text, valid_until: p.valid_until,
        vat_rate: p.vat_rate, currency: p.currency, contact: p.contact });
      setLines(p.items.map((i) => ({ ...i })));
      setDirty(false);
      setSendTo(p.contact?.email ?? p.sent_to ?? '');
    }
  }, [p]);

  if (isLoading) return <Center h="50vh"><Loader /></Center>;
  if (query.isError && !p) return <QueryFeedback query={query} />;
  if (!p) return <Empty text="КП не найдено или нет доступа" />;
  const locked = p.status === 'approved' || p.status === 'rejected';
  const editingDisabled = locked || saving || acting || sending;
  const set = (patch: Partial<ProposalDetail>) => { setForm({ ...form, ...patch }); setDirty(true); };
  const refresh = () => ['proposal', 'proposals', 'activities'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));

  const save = async (silent = false) => {
    setSaving(true);
    try {
      const { data: saved } = await api.patch<ProposalDetail>(`/proposals/${p.id}`, {
        title: form.title, intro_text: form.intro_text, terms_text: form.terms_text, valid_until: form.valid_until,
        vat_rate: form.vat_rate, currency: form.currency, contact_id: form.contact?.id ?? null,
        items: lines.filter((l) => l.name.trim()),
      });
      if (!silent) notifyOk('КП сохранено');
      setDirty(false);
      qc.setQueryData(['proposal', p.id, undefined], saved);
      refresh();
      return true;
    } catch (e) {
      notifyError(e);
      return false;
    } finally {
      setSaving(false);
    }
  };

  const savedAction = async (action: () => Promise<unknown>) => {
    if (busyRef.current) return;
    busyRef.current = true;
    setActing(true);
    try {
      if (dirtyRef.current && !(await save(true))) return;
      await action();
    } catch (e) {
      notifyError(e);
    } finally {
      busyRef.current = false;
      setActing(false);
    }
  };

  const preview = () => savedAction(() => openPdf(`/proposals/${p.id}/pdf`));
  const downloadPdf = () => savedAction(() => download(`/proposals/${p.id}/pdf`, { download: true }, `${p.number}.pdf`));

  const send = async () => {
    if (dirty && !(await save(true))) return;
    setSending(true);
    try {
      await api.post(`/proposals/${p.id}/send`, { to: sendTo, message: sendMsg || null });
      notifyOk('КП отправлено. Вы получите уведомление, когда клиент его откроет.');
      setSendOpen(false);
      refresh();
    } catch (e) {
      notifyError(e);
    } finally {
      setSending(false);
    }
  };

  const setStatus = (status: string) => savedAction(async () => {
      await api.patch(`/proposals/${p.id}`, { status });
      refresh();
  });

  const duplicate = () => savedAction(async () => {
      const { data } = await api.post(`/proposals/${p.id}/duplicate`);
      navigate(`/proposals/${data.id}`);
  });

  const invoice = () => savedAction(async () => {
      const { data } = await api.post('/invoices', { proposal_id: p.id });
      ['invoices', 'invoices-summary', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      notifyOk('Счёт выставлен по КП');
      navigate(`/finance?invoice=${data.id}`);
  });

  const remove = () => modals.openConfirmModal({
    title: 'Удалить черновик КП?', labels: { confirm: 'Удалить', cancel: 'Отмена' }, confirmProps: { color: 'red' },
    onConfirm: async () => {
      try {
        await api.delete(`/proposals/${p.id}`);
        setDirty(false);
        navigate('/proposals');
      } catch (e) {
        notifyError(e);
      }
    },
  });

  return (
    <>
      {query.isError && <QueryFeedback query={query} hasData />}
      <Modal opened={blocker.state === 'blocked'} onClose={() => blocker.reset?.()} title="Сохранить изменения КП?" centered>
        <Text size="sm" mb="md">В предложении есть несохранённые изменения.</Text>
        <Stack gap="xs">
          <Button loading={saving} disabled={acting || sending} onClick={async () => {
            if (await save()) blocker.proceed?.();
          }}>Сохранить и перейти</Button>
          <Button variant="default" disabled={saving || acting || sending} onClick={() => {
            setDirty(false); blocker.proceed?.();
          }}>Уйти без сохранения</Button>
          <Button variant="subtle" onClick={() => blocker.reset?.()}>Остаться</Button>
        </Stack>
      </Modal>
      <Anchor component={Link} to="/proposals" size="sm" c="dimmed">
        <Group gap={4}><IconArrowLeft size={14} /> Коммерческие предложения</Group>
      </Anchor>
      <Group justify="space-between" mt="xs" mb="md" align="flex-start">
        <div>
          <Group gap="sm">
            <Title order={2}>КП {p.number}</Title>
            <StatusBadge map={PROPOSAL_STATUS} value={p.status} size="lg" />
          </Group>
          <Text size="sm" c="dimmed" mt={4}>
            {p.company && <EntityLink to={`/companies/${p.company.id}`}>{p.company.name}</EntityLink>}
            {p.deal_id && <> · <EntityLink to={`/deals/${p.deal_id}`}>сделка</EntityLink></>}
          </Text>
        </div>
        <Group gap="xs">
          {dirty && <Button onClick={() => save()} loading={saving} disabled={acting || sending}>Сохранить</Button>}
          <Button variant="default" leftSection={<IconEye size={16} />} onClick={preview} disabled={saving || acting || sending}>PDF</Button>
          {!locked && <Button leftSection={<IconSend size={16} />} onClick={() => setSendOpen(true)} disabled={!lines.length || saving || acting || sending}>Отправить клиенту</Button>}
          <Menu position="bottom-end">
            <Menu.Target><Button variant="default" px="xs" aria-label="Ещё" disabled={saving || acting || sending}><IconDots size={18} /></Button></Menu.Target>
            <Menu.Dropdown>
              <Menu.Item leftSection={<IconDownload size={16} />} onClick={downloadPdf}>Скачать PDF</Menu.Item>
              <Menu.Item leftSection={<IconCopy size={16} />} onClick={duplicate}>Новая версия КП</Menu.Item>
              {p.status !== 'draft' && !locked && (
                <>
                  <Menu.Item leftSection={<IconCheck size={16} />} color="teal" onClick={() => setStatus('approved')}>Отметить: согласовано</Menu.Item>
                  <Menu.Item leftSection={<IconX size={16} />} color="red" onClick={() => setStatus('rejected')}>Отметить: отклонено</Menu.Item>
                </>
              )}
              <Menu.Item leftSection={<IconFileInvoice size={16} />} onClick={invoice}>Выставить счёт по КП</Menu.Item>
              {p.status === 'draft' && (
                <>
                  <Menu.Divider />
                  <Menu.Item leftSection={<IconTrash size={16} />} color="red" onClick={remove}>Удалить черновик</Menu.Item>
                </>
              )}
            </Menu.Dropdown>
          </Menu>
        </Group>
      </Group>
      {locked && (
        <Alert color={p.status === 'approved' ? 'teal' : 'red'} mb="md">
          КП {p.status === 'approved' ? 'согласовано' : 'отклонено'} {dateTime(p.decided_at)}.
          {p.client_comment && <> Комментарий клиента: «{p.client_comment}»</>} Для изменений создайте новую версию.
        </Alert>
      )}
      <Grid>
        <Grid.Col span={{ base: 12, lg: 9 }}>
          <Stack>
            <Card>
              <Stack>
                <TextInput label="Заголовок" value={form.title ?? ''} onChange={(e) => set({ title: e.currentTarget.value })} disabled={editingDisabled} />
                <SimpleGrid cols={{ base: 1, sm: 4 }}>
                  <ContactSelect label="Контактное лицо" companyId={p.company?.id} value={form.contact?.id ?? null} disabled={editingDisabled}
                    onChange={(v) => set({ contact: v ? { id: v, full_name: '' } : null })} />
                  <DatePickerInput label="Действует до" valueFormat="DD.MM.YYYY" disabled={editingDisabled}
                    value={form.valid_until ? new Date(form.valid_until) : null}
                    onChange={(d) => set({ valid_until: toISODate(d) ?? null })} />
                  <Select label="НДС" disabled={editingDisabled} allowDeselect={false} value={String(form.vat_rate ?? 20)}
                    data={[{ value: '20', label: '20%' }, { value: '10', label: '10%' }, { value: '0', label: 'Без НДС' }]}
                    onChange={(v) => set({ vat_rate: Number(v) })} />
                  <Select label="Валюта" data={CURRENCIES} disabled={editingDisabled} allowDeselect={false} value={form.currency ?? 'RUB'}
                    onChange={(v) => set({ currency: v! })} />
                </SimpleGrid>
                <div>
                  <Group justify="space-between" mb={4}>
                    <Text size="sm" fw={500}>Вступительный текст</Text>
                    {!editingDisabled && <VariablesHelp onInsert={(v) => set({ intro_text: `${form.intro_text ?? ''}${v}` })} />}
                  </Group>
                  <Textarea autosize minRows={3} value={form.intro_text ?? ''} disabled={editingDisabled} aria-label="Вступительный текст"
                    onChange={(e) => set({ intro_text: e.currentTarget.value })} />
                </div>
              </Stack>
            </Card>
            <Card>
              <Title order={5} mb="sm">Товары и услуги</Title>
              <LinesEditor lines={lines} onChange={(l) => { setLines(l); setDirty(true); }} currency={form.currency}
                vatRate={form.vat_rate} readOnly={editingDisabled} />
            </Card>
            <Card>
              <Group justify="space-between" mb={4}>
                <Text size="sm" fw={500}>Условия (оплата, поставка, гарантия)</Text>
                {!editingDisabled && <VariablesHelp onInsert={(v) => set({ terms_text: `${form.terms_text ?? ''}${v}` })} />}
              </Group>
              <Textarea autosize minRows={4} value={form.terms_text ?? ''} disabled={editingDisabled} aria-label="Условия"
                onChange={(e) => set({ terms_text: e.currentTarget.value })} />
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 3 }}>
          <Stack>
            <Card>
              <Title order={5} mb="md">Статус</Title>
              <Timeline active={[p.created_at, p.sent_at, p.viewed_at, p.decided_at].filter(Boolean).length - 1} bulletSize={18} lineWidth={2}>
                <Timeline.Item title="Создано"><Text size="xs" c="dimmed">{dateTime(p.created_at)}</Text></Timeline.Item>
                <Timeline.Item title="Отправлено"><Text size="xs" c="dimmed">{p.sent_at ? `${dateTime(p.sent_at)} · ${p.sent_to}` : '—'}</Text></Timeline.Item>
                <Timeline.Item title="Просмотрено клиентом"><Text size="xs" c="dimmed">{p.viewed_at ? dateTime(p.viewed_at) : '—'}</Text></Timeline.Item>
                <Timeline.Item title={p.status === 'rejected' ? 'Отклонено' : 'Согласовано'}>
                  <Text size="xs" c="dimmed">{p.decided_at ? dateTime(p.decided_at) : '—'}</Text>
                </Timeline.Item>
              </Timeline>
            </Card>
            {p.status !== 'draft' && p.public_url && (
              <Card>
                <Title order={5} mb="xs">Ссылка для клиента</Title>
                <Text size="xs" c="dimmed" mb="xs">Онлайн-версия КП с кнопками «Согласовать» / «Отклонить»</Text>
                <Group gap="xs">
                  <CopyButton value={p.public_url}>
                    {({ copied, copy }) => (
                      <Button size="xs" variant="light" leftSection={<IconLink size={14} />} onClick={copy} color={copied ? 'teal' : 'blue'}>
                        {copied ? 'Скопировано' : 'Копировать'}
                      </Button>
                    )}
                  </CopyButton>
                  <Button size="xs" variant="subtle" component="a" href={p.public_url.replace(/^https?:\/\/[^/]+/, '')} target="_blank">Открыть</Button>
                </Group>
              </Card>
            )}
            <Card>
              <Text size="xs" c="dimmed">Итого</Text>
              <Text fw={700} size="xl">{new Intl.NumberFormat('ru-RU', { style: 'currency', currency: p.currency }).format(p.total)}</Text>
              {dirty && <Badge color="orange" mt="xs">Есть несохранённые изменения</Badge>}
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      <Modal opened={sendOpen} onClose={() => setSendOpen(false)} title="Отправка КП клиенту" size="lg">
        <Stack>
          <TextInput label="Email получателя" value={sendTo} onChange={(e) => setSendTo(e.currentTarget.value)} />
          <Textarea label="Сопроводительный текст" placeholder="Оставьте пустым — используем стандартный текст" autosize minRows={5}
            value={sendMsg} onChange={(e) => setSendMsg(e.currentTarget.value)} />
          <Text size="xs" c="dimmed">
            К письму приложим PDF и ссылку на онлайн-версию. Факт открытия письма и КП отслеживается автоматически.
          </Text>
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setSendOpen(false)}>Отмена</Button>
            <Button leftSection={<IconSend size={16} />} onClick={send} loading={sending} disabled={!sendTo || saving || acting}>Отправить</Button>
          </Group>
        </Stack>
      </Modal>
    </>
  );
}
