import { useState } from 'react';
import {
  ActionIcon,
  Alert,
  Badge,
  Button,
  Code,
  CopyButton,
  Group,
  Menu,
  Modal,
  Paper,
  ScrollArea,
  Select,
  SimpleGrid,
  Stack,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconCheck, IconDots, IconKey, IconLock, IconLockOpen, IconPlus, IconShieldOff } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { modals } from '@mantine/modals';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { UserFull } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { dateTime } from '@/lib/format';
import { ROLE_LABELS } from '@/lib/labels';

const PERM_LABELS: Record<string, string> = {
  'companies.view_all': 'Видеть всех клиентов', 'leads.view_all': 'Видеть все лиды', 'deals.view_all': 'Видеть все сделки',
  'tasks.view_all': 'Видеть задачи всех', 'companies.edit': 'Создавать и изменять клиентов', 'companies.delete': 'Удалять клиентов',
  'companies.reassign': 'Передавать клиентов', 'leads.edit': 'Работать с лидами', 'leads.delete': 'Удалять лиды',
  'deals.view': 'Доступ к сделкам', 'deals.edit': 'Вести сделки', 'deals.delete': 'Удалять сделки', 'tasks.edit': 'Задачи',
  'proposals.edit': 'Коммерческие предложения', 'finance.view': 'Счета и оплаты (просмотр)', 'finance.edit': 'Счета и оплаты (изменение)',
  'analytics.view': 'Отчёты', 'analytics.team': 'Отчёты по всему отделу', 'marketing.edit': 'Маркетинговые бюджеты',
  import: 'Импорт', export: 'Экспорт базы', 'products.edit': 'Каталог продуктов', 'dictionaries.edit': 'Справочники',
  'pipeline.edit': 'Этапы воронки', 'templates.edit': 'Шаблоны КП', 'custom_fields.edit': 'Доп. поля',
  'users.manage': 'Пользователи', 'settings.manage': 'Настройки системы', 'audit.view': 'Журнал аудита',
  'integrations.manage': 'Интеграции',
};
const ROLES = Object.entries(ROLE_LABELS).map(([value, label]) => ({ value, label }));

function UserModal({ user, opened, onClose }: { user: UserFull | null; opened: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [password, setPassword] = useState<string | null>(null);
  const form = useForm({
    initialValues: {
      email: user?.email ?? '', full_name: user?.full_name ?? '', role: user?.role ?? 'manager',
      position: user?.position ?? '', phone: user?.phone ?? '', department: user?.department ?? '',
      sip_extension: user?.sip_extension ?? '',
    },
    validate: {
      email: (v: string) => (/^\S+@\S+\.\S+$/.test(v) ? null : 'Некорректный email'),
      full_name: (v: string) => (v.trim().length >= 2 ? null : 'Укажите ФИО'),
    },
  });
  const submit = form.onSubmit(async (values) => {
    try {
      if (user) {
        await api.patch(`/users/${user.id}`, values);
        notifyOk('Сохранено');
        onClose();
      } else {
        const { data } = await api.post('/users', values);
        setPassword(data.temporary_password);
      }
      qc.invalidateQueries({ queryKey: ['admin-users'] });
      qc.invalidateQueries({ queryKey: ['users-lookup'] });
    } catch (e) {
      notifyError(e);
    }
  });
  return (
    <Modal opened={opened} onClose={() => { setPassword(null); onClose(); }} title={user ? 'Пользователь' : 'Новый пользователь'} size="lg">
      {password ? (
        <Stack>
          <Alert color="teal" icon={<IconCheck />}>Пользователь создан. Данные для входа отправлены на email.</Alert>
          <Text size="sm">Временный пароль (будет запрошена смена при первом входе):</Text>
          <Group><Code fz="lg">{password}</Code>
            <CopyButton value={password}>{({ copied, copy }) => <Button size="xs" variant="light" onClick={copy}>{copied ? 'Скопирован' : 'Копировать'}</Button>}</CopyButton>
          </Group>
          <Button onClick={() => { setPassword(null); onClose(); }}>Готово</Button>
        </Stack>
      ) : (
        <form onSubmit={submit}>
          <Stack>
            <SimpleGrid cols={{ base: 1, sm: 2 }}>
              <TextInput label="ФИО" withAsterisk {...form.getInputProps('full_name')} />
              <TextInput label="Email (логин)" withAsterisk {...form.getInputProps('email')} />
              <Select label="Роль" data={ROLES} allowDeselect={false} {...form.getInputProps('role')} />
              <TextInput label="Должность" {...form.getInputProps('position')} />
              <TextInput label="Отдел" {...form.getInputProps('department')} />
              <TextInput label="Телефон" {...form.getInputProps('phone')} />
              <TextInput label="Внутренний номер SIP" description="Для телефонии: click-to-call и определение номера"
                {...form.getInputProps('sip_extension')} />
            </SimpleGrid>
            <Group justify="flex-end">
              <Button variant="default" onClick={onClose}>Отмена</Button>
              <Button type="submit">{user ? 'Сохранить' : 'Создать и отправить доступ'}</Button>
            </Group>
          </Stack>
        </form>
      )}
    </Modal>
  );
}

export default function UsersAdmin() {
  const { user: me } = useAuth();
  const qc = useQueryClient();
  const { data } = useApi<UserFull[]>(['admin-users'], '/users');
  const { data: roles } = useApi<{ matrix: Record<string, string[]> }>(['roles'], '/users/roles');
  const [editing, setEditing] = useState<UserFull | null>(null);
  const [open, setOpen] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ['admin-users'] });

  const toggleActive = async (u: UserFull) => {
    try {
      await api.patch(`/users/${u.id}`, { is_active: !u.is_active });
      notifyOk(u.is_active ? 'Учётная запись заблокирована, все сессии завершены' : 'Учётная запись разблокирована');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const resetPassword = (u: UserFull) => modals.openConfirmModal({
    title: 'Сбросить пароль?', labels: { confirm: 'Сбросить', cancel: 'Отмена' },
    children: <Text size="sm">Будет сгенерирован временный пароль и отправлен на {u.email}. Все сессии пользователя завершатся.</Text>,
    onConfirm: async () => {
      try {
        const { data: r } = await api.post(`/users/${u.id}/reset-password`);
        modals.open({ title: 'Временный пароль', children: <Stack><Code fz="lg">{r.temporary_password}</Code>
          <Text size="xs" c="dimmed">Также отправлен пользователю на email.</Text></Stack> });
      } catch (e) {
        notifyError(e);
      }
    },
  });
  const reset2fa = async (u: UserFull) => {
    try {
      await api.post(`/users/${u.id}/reset-2fa`);
      notifyOk('2FA отключена');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <Stack>
      <Group justify="flex-end">
        <Button leftSection={<IconPlus size={16} />} onClick={() => { setEditing(null); setOpen(true); }}>Пользователь</Button>
      </Group>
      <Paper withBorder>
        <Table.ScrollContainer minWidth={800}>
          <Table>
            <Table.Thead>
              <Table.Tr><Table.Th>Сотрудник</Table.Th><Table.Th>Роль</Table.Th><Table.Th>Отдел</Table.Th><Table.Th>Последний вход</Table.Th><Table.Th>Статус</Table.Th><Table.Th w={50} /></Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {data?.map((u) => (
                <Table.Tr key={u.id} opacity={u.is_active ? 1 : 0.55}>
                  <Table.Td>
                    <Text size="sm" fw={500}>{u.full_name}</Text>
                    <Text size="xs" c="dimmed">{u.email}{u.position ? ` · ${u.position}` : ''}</Text>
                  </Table.Td>
                  <Table.Td><Badge variant="light">{ROLE_LABELS[u.role]}</Badge></Table.Td>
                  <Table.Td>{u.department ?? '—'}</Table.Td>
                  <Table.Td>{u.last_login ? dateTime(u.last_login) : 'не входил'}</Table.Td>
                  <Table.Td>
                    <Group gap={4}>
                      {u.is_active ? <Badge color="teal">Активен</Badge> : <Badge color="gray">Заблокирован</Badge>}
                      {u.totp_enabled && <Badge color="blue" variant="outline">2FA</Badge>}
                    </Group>
                  </Table.Td>
                  <Table.Td>
                    <Menu position="bottom-end">
                      <Menu.Target><ActionIcon variant="subtle" aria-label="Действия"><IconDots size={16} /></ActionIcon></Menu.Target>
                      <Menu.Dropdown>
                        <Menu.Item onClick={() => { setEditing(u); setOpen(true); }}>Редактировать</Menu.Item>
                        <Menu.Item leftSection={<IconKey size={14} />} onClick={() => resetPassword(u)}>Сбросить пароль</Menu.Item>
                        {u.totp_enabled && <Menu.Item leftSection={<IconShieldOff size={14} />} onClick={() => reset2fa(u)}>Отключить 2FA</Menu.Item>}
                        {u.id !== me?.id && (
                          <Menu.Item color={u.is_active ? 'red' : 'teal'} leftSection={u.is_active ? <IconLock size={14} /> : <IconLockOpen size={14} />}
                            onClick={() => toggleActive(u)}>
                            {u.is_active ? 'Заблокировать' : 'Разблокировать'}
                          </Menu.Item>
                        )}
                      </Menu.Dropdown>
                    </Menu>
                  </Table.Td>
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </Table.ScrollContainer>
      </Paper>
      <Paper withBorder p="md">
        <Title order={5} mb="sm">Ролевая модель</Title>
        <ScrollArea>
          <Table withColumnBorders fz="sm" miw={700}>
            <Table.Thead>
              <Table.Tr><Table.Th>Право</Table.Th>{ROLES.map((r) => <Table.Th key={r.value} ta="center">{r.label}</Table.Th>)}</Table.Tr>
            </Table.Thead>
            <Table.Tbody>
              {Object.entries(roles?.matrix ?? {}).map(([perm, rs]) => (
                <Table.Tr key={perm}>
                  <Table.Td>{PERM_LABELS[perm] ?? perm}</Table.Td>
                  {ROLES.map((r) => <Table.Td key={r.value} ta="center">{rs.includes(r.value) ? <IconCheck size={16} color="var(--mantine-color-teal-6)" /> : ''}</Table.Td>)}
                </Table.Tr>
              ))}
            </Table.Tbody>
          </Table>
        </ScrollArea>
        <Text size="xs" c="dimmed" mt="sm">Менеджер без права «Видеть все …» работает только со своими клиентами, лидами, сделками и задачами.</Text>
      </Paper>
      {open && <UserModal user={editing} opened={open} onClose={() => setOpen(false)} />}
    </Stack>
  );
}
