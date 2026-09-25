import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Alert,
  Anchor,
  Button,
  Card,
  Center,
  Grid,
  Group,
  Loader,
  Modal,
  NumberInput,
  Radio,
  SimpleGrid,
  Stack,
  Text,
  Textarea,
  TextInput,
  Title,
} from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { IconArrowLeft, IconBan, IconEdit, IconMail, IconPlayerPlay, IconTransform } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Lead } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { CustomFieldsView } from '@/components/CustomFields';
import EmailModal from '@/components/EmailModal';
import { LeadModal } from '@/components/forms';
import { CompanySelect, DictSelect, StageSelect } from '@/components/selects';
import TasksPanel from '@/components/TasksPanel';
import Timeline from '@/components/Timeline';
import { Empty, EntityLink, Field, Phone, StatusBadge } from '@/components/ui';
import { dateTime, dayjs, money, toISODate } from '@/lib/format';
import { LEAD_STATUS } from '@/lib/labels';

interface Duplicates {
  companies: { id: number; name: string; inn: string | null; manager: string | null }[];
  contacts: { id: number; full_name: string; company_id: number | null; company: string | null }[];
}

function ConvertModal({ lead, opened, onClose }: { lead: Lead; opened: boolean; onClose: () => void }) {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { data: dups } = useApi<Duplicates>(['lead-dups', lead.id], opened ? `/leads/${lead.id}/duplicates` : null);
  const [mode, setMode] = useState<'new' | 'existing'>('new');
  const [companyId, setCompanyId] = useState<number | null>(null);
  const [companyName, setCompanyName] = useState(lead.company_name ?? '');
  const [title, setTitle] = useState(lead.title);
  const [amount, setAmount] = useState<number | string>(lead.estimated_amount ?? 0);
  const [stageId, setStageId] = useState<number | null>(null);
  const [closeDate, setCloseDate] = useState<Date | null>(dayjs().add(30, 'day').toDate());
  const [saving, setSaving] = useState(false);
  useEffect(() => {
    if (dups?.companies.length) {
      setMode('existing');
      setCompanyId(dups.companies[0].id);
    }
  }, [dups]);

  const submit = async () => {
    setSaving(true);
    try {
      const { data } = await api.post(`/leads/${lead.id}/convert`, {
        company_id: mode === 'existing' ? companyId : null, company_name: companyName, deal_title: title,
        amount: Number(amount || 0), stage_id: stageId, close_date: toISODate(closeDate),
        contact_id: mode === 'existing' && dups?.contacts[0]?.company_id === companyId ? dups?.contacts[0]?.id : null,
      });
      notifyOk('Лид конвертирован: созданы сделка, компания и контакт');
      ['leads', 'lead', 'lead-stats', 'deals', 'companies'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      navigate(`/deals/${data.deal_id}`);
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Конвертация лида в сделку" size="lg">
      <Stack>
        {!!dups?.companies.length && (
          <Alert color="blue" title="Похоже, клиент уже есть в базе">
            {dups.companies.map((c) => `${c.name}${c.inn ? ` (ИНН ${c.inn})` : ''}${c.manager ? ` — ${c.manager}` : ''}`).join('; ')}
          </Alert>
        )}
        <Radio.Group label="Компания" value={mode} onChange={(v) => setMode(v as 'new' | 'existing')}>
          <Group mt="xs">
            <Radio value="new" label="Создать новую" />
            <Radio value="existing" label="Выбрать из базы" />
          </Group>
        </Radio.Group>
        {mode === 'new' ? (
          <TextInput label="Название компании" value={companyName} onChange={(e) => setCompanyName(e.currentTarget.value)} />
        ) : (
          <CompanySelect label="Компания" value={companyId} onChange={setCompanyId}
            initial={dups?.companies.find((c) => c.id === companyId) ?? null} />
        )}
        <TextInput label="Название сделки" value={title} onChange={(e) => setTitle(e.currentTarget.value)} />
        <SimpleGrid cols={{ base: 1, sm: 3 }}>
          <NumberInput label="Сумма, ₽" value={amount} onChange={setAmount} thousandSeparator=" " min={0} />
          <StageSelect label="Этап" openOnly value={stageId} onChange={setStageId} placeholder="Первый этап" />
          <DatePickerInput label="Плановое закрытие" value={closeDate} onChange={setCloseDate} valueFormat="DD.MM.YYYY" />
        </SimpleGrid>
        <Text size="xs" c="dimmed">
          Контактное лицо из заявки будет создано и привязано к компании и сделке автоматически.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button onClick={submit} loading={saving} disabled={mode === 'existing' && !companyId} leftSection={<IconTransform size={16} />}>
            Создать сделку
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}

function RejectModal({ lead, opened, onClose }: { lead: Lead; opened: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [reason, setReason] = useState<number | null>(null);
  const [comment, setComment] = useState('');
  const submit = async () => {
    try {
      await api.post(`/leads/${lead.id}/reject`, { reason_id: reason, comment });
      notifyOk('Лид отклонён');
      ['leads', 'lead', 'lead-stats', 'activities'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      onClose();
    } catch (e) {
      notifyError(e);
    }
  };
  return (
    <Modal opened={opened} onClose={onClose} title="Отклонить лид">
      <Stack>
        <DictSelect kind="loss_reason" label="Причина" withAsterisk value={reason} onChange={setReason} />
        <Textarea label="Комментарий" value={comment} onChange={(e) => setComment(e.currentTarget.value)} autosize minRows={2} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button color="red" onClick={submit} disabled={!reason}>Отклонить</Button>
        </Group>
      </Stack>
    </Modal>
  );
}

export default function LeadCard() {
  const { id } = useParams();
  const { can } = useAuth();
  const qc = useQueryClient();
  const [edit, setEdit] = useState(false);
  const [convert, setConvert] = useState(false);
  const [reject, setReject] = useState(false);
  const [email, setEmail] = useState(false);
  const { data: l, isLoading } = useApi<Lead>(['lead', Number(id)], `/leads/${id}`);
  if (isLoading) return <Center h="50vh"><Loader /></Center>;
  if (!l) return <Empty text="Лид не найден или нет доступа" />;
  const closed = l.status === 'qualified' || l.status === 'rejected';

  const take = async () => {
    try {
      await api.post(`/leads/${l.id}/take`);
      ['lead', 'leads', 'lead-stats', 'activities'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <>
      <Anchor component={Link} to="/leads" size="sm" c="dimmed">
        <Group gap={4}><IconArrowLeft size={14} /> Лиды</Group>
      </Anchor>
      <Group justify="space-between" mt="xs" mb="md" align="flex-start">
        <div style={{ flex: 1, minWidth: 0 }}>
          <Group gap="sm">
            <Title order={2}>{l.title}</Title>
            <StatusBadge map={LEAD_STATUS} value={l.status} size="md" />
          </Group>
          <Text c="dimmed" size="sm" mt={4}>
            {l.source?.name ?? 'Источник не указан'} · поступил {dateTime(l.created_at)}
            {l.first_response_at && ` · первый ответ через ${Math.max(1, dayjs(l.first_response_at).diff(l.created_at, 'minute'))} мин`}
          </Text>
        </div>
        <Group gap="xs">
          {l.email && <Button variant="default" leftSection={<IconMail size={16} />} onClick={() => setEmail(true)}>Письмо</Button>}
          {!closed && l.status === 'new' && (
            <Button variant="default" leftSection={<IconPlayerPlay size={16} />} onClick={take}>Взять в работу</Button>
          )}
          {!closed && can('leads.edit') && <Button variant="default" leftSection={<IconEdit size={16} />} onClick={() => setEdit(true)}>Изменить</Button>}
          {!closed && can('leads.edit') && <Button variant="light" color="red" leftSection={<IconBan size={16} />} onClick={() => setReject(true)}>Отклонить</Button>}
          {!closed && can('deals.edit') && <Button leftSection={<IconTransform size={16} />} onClick={() => setConvert(true)}>Конвертировать в сделку</Button>}
        </Group>
      </Group>
      {l.status === 'qualified' && l.deal_id && (
        <Alert color="teal" mb="md">
          Лид квалифицирован: <EntityLink to={`/deals/${l.deal_id}`}>открыть сделку</EntityLink>
          {l.company_id && <> · <EntityLink to={`/companies/${l.company_id}`}>карточка компании</EntityLink></>}
        </Alert>
      )}
      {l.status === 'rejected' && (
        <Alert color="gray" mb="md">
          Отклонён: {l.reject_reason?.name}{l.reject_comment ? ` — ${l.reject_comment}` : ''}
        </Alert>
      )}
      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Card>
            <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
              <Field label="Компания">{l.company_name}</Field>
              <Field label="ИНН">{l.inn}</Field>
              <Field label="Контактное лицо">{[l.contact_name, l.contact_position].filter(Boolean).join(', ')}</Field>
              <Field label="Телефон"><Phone phone={l.phone} links={{ lead_id: l.id }} /></Field>
              <Field label="Email">{l.email}</Field>
              <Field label="Бюджет">{l.estimated_amount ? money(l.estimated_amount) : null}</Field>
              <Field label="Ответственный">{l.assignee?.full_name}</Field>
              {(l.utm_source || l.utm_campaign) && (
                <Field label="UTM">{[l.utm_source, l.utm_medium, l.utm_campaign].filter(Boolean).join(' / ')}</Field>
              )}
              <CustomFieldsView entity="lead" value={l.custom_fields} />
            </SimpleGrid>
            {l.message && (
              <>
                <Text size="xs" c="dimmed" mt="md">Сообщение</Text>
                <Text size="sm" style={{ whiteSpace: 'pre-wrap' }}>{l.message}</Text>
              </>
            )}
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card>
              <Title order={5} mb="xs">Задачи</Title>
              <TasksPanel defaults={{ lead_id: l.id }} />
            </Card>
            <Card>
              <Title order={5} mb="sm">Лента событий</Title>
              <Timeline filter={{ lead_id: l.id }} />
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      <LeadModal opened={edit} onClose={() => setEdit(false)} lead={l} />
      <ConvertModal lead={l} opened={convert} onClose={() => setConvert(false)} />
      <RejectModal lead={l} opened={reject} onClose={() => setReject(false)} />
      <EmailModal opened={email} onClose={() => setEmail(false)} to={l.email} links={{ lead_id: l.id }} />
    </>
  );
}
