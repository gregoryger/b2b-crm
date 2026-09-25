import { useEffect, useState } from 'react';
import {
  Accordion,
  Alert,
  Button,
  Group,
  Modal,
  NumberInput,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Textarea,
  TextInput,
} from '@mantine/core';
import { DatePickerInput, DateTimePicker } from '@mantine/dates';
import { useForm } from '@mantine/form';
import { IconAlertTriangle } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import type { Company, Contact, Deal, DealDetail, Lead, Task } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { dayjs, toISODate } from '@/lib/format';
import { COMPANY_STATUS, CONTACT_ROLES, CURRENCIES, PRIORITIES, REMINDERS, TASK_TYPES } from '@/lib/labels';
import { CustomFieldsInputs } from './CustomFields';
import { CompanySelect, ContactSelect, DictSelect, StageSelect, UserSelect } from './selects';

const opts = (m: Record<string, { label: string } | string>) =>
  Object.entries(m).map(([value, v]) => ({ value, label: typeof v === 'string' ? v : v.label }));

function useSave<T>(invalidate: string[]) {
  const qc = useQueryClient();
  const [saving, setSaving] = useState(false);
  const run = async (fn: () => Promise<T>, ok: string): Promise<T | null> => {
    setSaving(true);
    try {
      const r = await fn();
      invalidate.forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
      notifyOk(ok);
      return r;
    } catch (e) {
      notifyError(e);
      return null;
    } finally {
      setSaving(false);
    }
  };
  return { saving, run };
}

// ---------------- Компания ----------------

export function CompanyModal({ opened, onClose, company, onSaved }: {
  opened: boolean; onClose: () => void; company?: Company | null; onSaved?: (c: Company) => void;
}) {
  const { can } = useAuth();
  const { saving, run } = useSave<Company>(['companies', 'company', 'companies-lookup', 'activities']);
  const [dup, setDup] = useState<string | null>(null);
  const empty = {
    name: '', full_name: '', inn: '', kpp: '', ogrn: '', legal_address: '', actual_address: '', bank_name: '',
    bik: '', account: '', corr_account: '', industry_id: null as number | null, region_id: null as number | null,
    client_type_id: null as number | null, source_id: null as number | null, manager_id: null as number | null,
    status: 'prospect', phone: '', email: '', website: '', description: '', custom_fields: {} as Record<string, unknown>,
  };
  const form = useForm({
    initialValues: empty,
    validate: {
      name: (v: string) => (v.trim() ? null : 'Укажите наименование'),
      inn: (v: string) => (!v || /^\d{10}$|^\d{12}$/.test(v) ? null : 'ИНН — 10 или 12 цифр'),
      email: (v: string) => (!v || /^\S+@\S+\.\S+$/.test(v) ? null : 'Некорректный email'),
    },
  });
  useEffect(() => {
    if (!opened) return;
    setDup(null);
    if (company) {
      form.setValues({
        ...empty,
        ...Object.fromEntries(Object.entries(company).filter(([k]) => k in empty).map(([k, v]) => [k, v ?? ''])),
        industry_id: company.industry?.id ?? null, region_id: company.region?.id ?? null,
        client_type_id: company.client_type?.id ?? null, source_id: company.source?.id ?? null,
        manager_id: company.manager?.id ?? null, custom_fields: company.custom_fields ?? {},
      } as typeof empty);
    } else form.setValues(empty);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, company]);

  const checkInn = async () => {
    const inn = form.values.inn;
    if (!/^\d{10}$|^\d{12}$/.test(inn)) return setDup(null);
    const { data } = await api.get('/companies/check-inn', { params: { inn, exclude_id: company?.id } });
    setDup(data.exists ? `Компания с этим ИНН уже есть: «${data.name}»${data.manager ? `, ответственный — ${data.manager}` : ''}` : null);
  };

  const submit = form.onSubmit(async (values) => {
    const body = { ...values };
    if (!can('companies.reassign')) delete (body as Partial<typeof body>).manager_id;
    const r = await run(async () => (company
      ? (await api.patch<Company>(`/companies/${company.id}`, body)).data
      : (await api.post<Company>('/companies', body)).data), company ? 'Компания сохранена' : 'Компания добавлена');
    if (r) {
      onSaved?.(r);
      onClose();
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={company ? 'Редактирование компании' : 'Новая компания'} size="xl">
      <form onSubmit={submit}>
        <Stack>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput label="Наименование" withAsterisk data-autofocus {...form.getInputProps('name')} />
            <TextInput label="ИНН" {...form.getInputProps('inn')} onBlur={checkInn} maxLength={12} />
          </SimpleGrid>
          {dup && (
            <Alert color="orange" icon={<IconAlertTriangle size={18} />} py="xs">
              {dup}
            </Alert>
          )}
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <DictSelect kind="industry" label="Отрасль" {...form.getInputProps('industry_id')} />
            <DictSelect kind="region" label="Регион" {...form.getInputProps('region_id')} />
            <DictSelect kind="client_type" label="Тип клиента" {...form.getInputProps('client_type_id')} />
            <Select label="Статус" data={opts(COMPANY_STATUS)} allowDeselect={false} {...form.getInputProps('status')} />
            <DictSelect kind="lead_source" label="Источник" {...form.getInputProps('source_id')} />
            {can('companies.reassign') && (
              <UserSelect label="Ответственный" role="manager,head" {...form.getInputProps('manager_id')} />
            )}
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <TextInput label="Телефон" placeholder="+7 (___) ___-__-__" {...form.getInputProps('phone')} />
            <TextInput label="Email" {...form.getInputProps('email')} />
            <TextInput label="Сайт" {...form.getInputProps('website')} />
          </SimpleGrid>
          <Accordion variant="contained" chevronPosition="left">
            <Accordion.Item value="req">
              <Accordion.Control>Реквизиты и адреса</Accordion.Control>
              <Accordion.Panel>
                <Stack>
                  <TextInput label="Полное наименование" {...form.getInputProps('full_name')} />
                  <SimpleGrid cols={{ base: 1, sm: 2 }}>
                    <TextInput label="КПП" maxLength={9} {...form.getInputProps('kpp')} />
                    <TextInput label="ОГРН" maxLength={15} {...form.getInputProps('ogrn')} />
                  </SimpleGrid>
                  <TextInput label="Юридический адрес" {...form.getInputProps('legal_address')} />
                  <TextInput label="Фактический адрес" {...form.getInputProps('actual_address')} />
                  <SimpleGrid cols={{ base: 1, sm: 2 }}>
                    <TextInput label="Банк" {...form.getInputProps('bank_name')} />
                    <TextInput label="БИК" maxLength={9} {...form.getInputProps('bik')} />
                    <TextInput label="Расчётный счёт" maxLength={20} {...form.getInputProps('account')} />
                    <TextInput label="Корр. счёт" maxLength={20} {...form.getInputProps('corr_account')} />
                  </SimpleGrid>
                </Stack>
              </Accordion.Panel>
            </Accordion.Item>
          </Accordion>
          <CustomFieldsInputs entity="company" value={form.values.custom_fields}
            onChange={(v) => form.setFieldValue('custom_fields', v)} />
          <Textarea label="Описание" autosize minRows={2} {...form.getInputProps('description')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={saving}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

// ---------------- Контакт ----------------

export function ContactModal({ opened, onClose, contact, companyId, onSaved }: {
  opened: boolean; onClose: () => void; contact?: Contact | null; companyId?: number | null;
  onSaved?: (c: Contact) => void;
}) {
  const { saving, run } = useSave<Contact>(['contacts', 'contact', 'contacts-lookup', 'activities']);
  const empty = {
    company_id: null as number | null, last_name: '', first_name: '', middle_name: '', position: '',
    phone_mobile: '', phone_work: '', email: '', telegram: '', whatsapp: '', role_in_deal: null as string | null,
    notes: '', custom_fields: {} as Record<string, unknown>,
  };
  const form = useForm({
    initialValues: empty,
    validate: {
      last_name: (v: string) => (v.trim() ? null : 'Укажите фамилию'),
      first_name: (v: string) => (v.trim() ? null : 'Укажите имя'),
      email: (v: string) => (!v || /^\S+@\S+\.\S+$/.test(v) ? null : 'Некорректный email'),
    },
  });
  useEffect(() => {
    if (!opened) return;
    if (contact) {
      form.setValues({
        ...empty,
        ...Object.fromEntries(Object.entries(contact).filter(([k]) => k in empty).map(([k, v]) => [k, v ?? ''])),
        company_id: contact.company?.id ?? null, role_in_deal: contact.role_in_deal,
        custom_fields: contact.custom_fields ?? {},
      } as typeof empty);
    } else form.setValues({ ...empty, company_id: companyId ?? null });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, contact, companyId]);

  const submit = form.onSubmit(async (values) => {
    const r = await run(async () => (contact
      ? (await api.patch<Contact>(`/contacts/${contact.id}`, values)).data
      : (await api.post<Contact>('/contacts', values)).data), contact ? 'Контакт сохранён' : 'Контакт добавлен');
    if (r) {
      onSaved?.(r);
      onClose();
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={contact ? 'Редактирование контакта' : 'Новый контакт'} size="lg">
      <form onSubmit={submit}>
        <Stack>
          <CompanySelect label="Компания" initial={contact?.company} {...form.getInputProps('company_id')} />
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <TextInput label="Фамилия" withAsterisk data-autofocus {...form.getInputProps('last_name')} />
            <TextInput label="Имя" withAsterisk {...form.getInputProps('first_name')} />
            <TextInput label="Отчество" {...form.getInputProps('middle_name')} />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <TextInput label="Должность" {...form.getInputProps('position')} />
            <Select label="Роль в сделке" clearable data={opts(CONTACT_ROLES)} {...form.getInputProps('role_in_deal')} />
            <TextInput label="Мобильный телефон" {...form.getInputProps('phone_mobile')} />
            <TextInput label="Рабочий телефон" {...form.getInputProps('phone_work')} />
            <TextInput label="Email" {...form.getInputProps('email')} />
            <TextInput label="Telegram" placeholder="@username" {...form.getInputProps('telegram')} />
            <TextInput label="WhatsApp" {...form.getInputProps('whatsapp')} />
          </SimpleGrid>
          <CustomFieldsInputs entity="contact" value={form.values.custom_fields}
            onChange={(v) => form.setFieldValue('custom_fields', v)} />
          <Textarea label="Заметки" autosize minRows={2} {...form.getInputProps('notes')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={saving}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

// ---------------- Лид ----------------

export function LeadModal({ opened, onClose, lead, onSaved }: {
  opened: boolean; onClose: () => void; lead?: Lead | null; onSaved?: (l: Lead) => void;
}) {
  const { can } = useAuth();
  const { saving, run } = useSave<Lead>(['leads', 'lead', 'lead-stats']);
  const empty = {
    title: '', source_id: null as number | null, assigned_to: null as number | null, company_name: '', inn: '',
    contact_name: '', contact_position: '', phone: '', email: '', message: '',
    estimated_amount: '' as number | string, custom_fields: {} as Record<string, unknown>,
  };
  const form = useForm({
    initialValues: empty,
    validate: {
      title: (v: string) => (v.trim() ? null : 'Кратко опишите запрос'),
      email: (v: string) => (!v || /^\S+@\S+\.\S+$/.test(v) ? null : 'Некорректный email'),
    },
  });
  useEffect(() => {
    if (!opened) return;
    if (lead) {
      form.setValues({
        ...empty,
        ...Object.fromEntries(Object.entries(lead).filter(([k]) => k in empty).map(([k, v]) => [k, v ?? ''])),
        source_id: lead.source?.id ?? null, assigned_to: lead.assignee?.id ?? null,
        custom_fields: lead.custom_fields ?? {},
      } as typeof empty);
    } else form.setValues(empty);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, lead]);

  const submit = form.onSubmit(async (values) => {
    const body = { ...values, estimated_amount: values.estimated_amount === '' ? null : values.estimated_amount };
    const r = await run(async () => (lead
      ? (await api.patch<Lead>(`/leads/${lead.id}`, body)).data
      : (await api.post<Lead>('/leads', body)).data), lead ? 'Лид сохранён' : 'Лид создан');
    if (r) {
      onSaved?.(r);
      onClose();
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={lead ? 'Редактирование лида' : 'Новый лид'} size="lg">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Запрос" placeholder="Например: нужна поставка 20 ноутбуков" withAsterisk data-autofocus
            {...form.getInputProps('title')} />
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <DictSelect kind="lead_source" label="Источник" {...form.getInputProps('source_id')} />
            {can('leads.view_all') && (
              <UserSelect label="Ответственный" role="manager,head" placeholder="Автоматически"
                {...form.getInputProps('assigned_to')} />
            )}
            <TextInput label="Компания" {...form.getInputProps('company_name')} />
            <TextInput label="ИНН" maxLength={12} {...form.getInputProps('inn')} />
            <TextInput label="Контактное лицо" {...form.getInputProps('contact_name')} />
            <TextInput label="Должность" {...form.getInputProps('contact_position')} />
            <TextInput label="Телефон" {...form.getInputProps('phone')} />
            <TextInput label="Email" {...form.getInputProps('email')} />
            <NumberInput label="Ориентировочный бюджет, ₽" min={0} thousandSeparator=" "
              {...form.getInputProps('estimated_amount')} />
          </SimpleGrid>
          <CustomFieldsInputs entity="lead" value={form.values.custom_fields}
            onChange={(v) => form.setFieldValue('custom_fields', v)} />
          <Textarea label="Сообщение / комментарий" autosize minRows={2} {...form.getInputProps('message')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={saving}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

// ---------------- Сделка ----------------

export function DealModal({ opened, onClose, deal, defaults, onSaved }: {
  opened: boolean; onClose: () => void; deal?: Deal | DealDetail | null;
  defaults?: { company_id?: number | null; contact_id?: number | null; stage_id?: number | null };
  onSaved?: (d: DealDetail) => void;
}) {
  const { can } = useAuth();
  const { saving, run } = useSave<DealDetail>(['deals', 'deal', 'board', 'company', 'activities', 'dashboard']);
  const empty = {
    title: '', company_id: null as number | null, contact_id: null as number | null, stage_id: null as number | null,
    owner_id: null as number | null, amount: 0 as number | string, currency: 'RUB',
    close_date: dayjs().add(30, 'day').toDate() as Date | null, description: '',
    custom_fields: {} as Record<string, unknown>,
  };
  const form = useForm({
    initialValues: empty,
    validate: { title: (v: string) => (v.trim() ? null : 'Укажите название сделки') },
  });
  useEffect(() => {
    if (!opened) return;
    if (deal) {
      form.setValues({
        title: deal.title, company_id: deal.company?.id ?? null, contact_id: deal.contact?.id ?? null,
        stage_id: deal.stage.id, owner_id: deal.owner?.id ?? null, amount: deal.amount, currency: deal.currency,
        close_date: deal.close_date ? new Date(deal.close_date) : null, description: deal.description ?? '',
        custom_fields: deal.custom_fields ?? {},
      });
    } else form.setValues({ ...empty, ...defaults });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, deal]);

  const submit = form.onSubmit(async (values) => {
    const body = { ...values, amount: Number(values.amount || 0), close_date: toISODate(values.close_date) ?? null };
    if (!can('deals.view_all')) delete (body as Partial<typeof body>).owner_id;
    if (deal) delete (body as Partial<typeof body>).stage_id;
    const r = await run(async () => (deal
      ? (await api.patch<DealDetail>(`/deals/${deal.id}`, body)).data
      : (await api.post<DealDetail>('/deals', body)).data), deal ? 'Сделка сохранена' : 'Сделка создана');
    if (r) {
      onSaved?.(r);
      onClose();
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={deal ? 'Редактирование сделки' : 'Новая сделка'} size="lg">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Название" placeholder="Например: Поставка серверов" withAsterisk data-autofocus
            {...form.getInputProps('title')} />
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <CompanySelect label="Компания" initial={deal?.company} value={form.values.company_id}
              onChange={(v) => {
                form.setFieldValue('company_id', v);
                form.setFieldValue('contact_id', null);
              }} />
            <ContactSelect label="Контактное лицо" companyId={form.values.company_id}
              {...form.getInputProps('contact_id')} />
          </SimpleGrid>
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <NumberInput label="Сумма" min={0} thousandSeparator=" " decimalScale={2}
              {...form.getInputProps('amount')} />
            <Select label="Валюта" data={CURRENCIES} allowDeselect={false} {...form.getInputProps('currency')} />
            <DatePickerInput label="Плановая дата закрытия" valueFormat="DD.MM.YYYY" clearable
              {...form.getInputProps('close_date')} />
            {!deal && <StageSelect label="Этап" openOnly placeholder="Первый этап" {...form.getInputProps('stage_id')} />}
            {can('deals.view_all') && (
              <UserSelect label="Ответственный" role="manager,head" placeholder="Я"
                {...form.getInputProps('owner_id')} />
            )}
          </SimpleGrid>
          <CustomFieldsInputs entity="deal" value={form.values.custom_fields}
            onChange={(v) => form.setFieldValue('custom_fields', v)} />
          <Textarea label="Описание" autosize minRows={2} {...form.getInputProps('description')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={saving}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}

// ---------------- Задача ----------------

export interface TaskDefaults {
  deal_id?: number | null;
  company_id?: number | null;
  contact_id?: number | null;
  lead_id?: number | null;
  due_at?: Date;
  type?: Task['type'];
  title?: string;
}

export function TaskModal({ opened, onClose, task, defaults, onSaved }: {
  opened: boolean; onClose: () => void; task?: Task | null; defaults?: TaskDefaults; onSaved?: (t: Task) => void;
}) {
  const { user } = useAuth();
  const { saving, run } = useSave<Task>(['tasks', 'task', 'dashboard', 'calendar', 'activities']);
  const nextSlot = () => {
    const d = dayjs().add(1, 'hour').minute(0).second(0);
    return (d.hour() > 18 ? d.add(1, 'day').hour(10) : d).toDate();
  };
  const empty = {
    title: '', type: 'call' as Task['type'], priority: 'medium' as Task['priority'], due_at: nextSlot() as Date | null,
    duration_minutes: 30 as number | string, assignee_id: user?.id ?? null as number | null,
    reminder_minutes: '60', description: '',
  };
  const form = useForm({
    initialValues: empty,
    validate: {
      title: (v: string) => (v.trim() ? null : 'Что нужно сделать?'),
      due_at: (v: Date | null) => (v ? null : 'Укажите срок'),
    },
  });
  useEffect(() => {
    if (!opened) return;
    if (task) {
      form.setValues({
        title: task.title, type: task.type, priority: task.priority, due_at: new Date(task.due_at),
        duration_minutes: task.duration_minutes, assignee_id: task.assignee?.id ?? null,
        reminder_minutes: task.reminder_minutes ? String(task.reminder_minutes) : '', description: task.description ?? '',
      });
    } else form.setValues({ ...empty, ...defaults, due_at: defaults?.due_at ?? nextSlot() });
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [opened, task]);

  const submit = form.onSubmit(async (values) => {
    const body = {
      ...values,
      due_at: values.due_at?.toISOString(),
      duration_minutes: Number(values.duration_minutes || 30),
      reminder_minutes: values.reminder_minutes ? Number(values.reminder_minutes) : null,
      ...(task ? {} : {
        deal_id: defaults?.deal_id ?? null, company_id: defaults?.company_id ?? null,
        contact_id: defaults?.contact_id ?? null, lead_id: defaults?.lead_id ?? null,
      }),
    };
    const r = await run(async () => (task
      ? (await api.patch<Task>(`/tasks/${task.id}`, body)).data
      : (await api.post<Task>('/tasks', body)).data), task ? 'Задача сохранена' : 'Задача создана');
    if (r) {
      onSaved?.(r);
      onClose();
    }
  });

  return (
    <Modal opened={opened} onClose={onClose} title={task ? 'Задача' : 'Новая задача'} size="lg">
      <form onSubmit={submit}>
        <Stack>
          <SegmentedControl fullWidth data={opts(TASK_TYPES)} {...form.getInputProps('type')} />
          <TextInput label="Что сделать" withAsterisk data-autofocus {...form.getInputProps('title')} />
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <DateTimePicker label="Срок" withAsterisk valueFormat="DD.MM.YYYY HH:mm" {...form.getInputProps('due_at')} />
            <Select label="Длительность" allowDeselect={false}
              data={[{ value: '15', label: '15 мин' }, { value: '30', label: '30 мин' }, { value: '60', label: '1 час' },
                { value: '90', label: '1,5 часа' }, { value: '120', label: '2 часа' }, { value: '240', label: '4 часа' }]}
              value={String(form.values.duration_minutes)}
              onChange={(v) => form.setFieldValue('duration_minutes', Number(v))} />
            <UserSelect label="Исполнитель" {...form.getInputProps('assignee_id')} />
            <Select label="Приоритет" data={opts(PRIORITIES)} allowDeselect={false} {...form.getInputProps('priority')} />
            <Select label="Напоминание" data={REMINDERS} allowDeselect={false} {...form.getInputProps('reminder_minutes')} />
          </SimpleGrid>
          <Textarea label="Описание" autosize minRows={2} {...form.getInputProps('description')} />
          <Group justify="flex-end">
            <Button variant="default" onClick={onClose}>
              Отмена
            </Button>
            <Button type="submit" loading={saving}>
              Сохранить
            </Button>
          </Group>
        </Stack>
      </form>
    </Modal>
  );
}
