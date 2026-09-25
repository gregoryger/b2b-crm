import { useState } from 'react';
import { Link, NavLink as RouterNavLink, Outlet, useLocation, useNavigate } from 'react-router-dom';
import {
  ActionIcon,
  AppShell,
  Avatar,
  Burger,
  Button,
  Group,
  Kbd,
  Menu,
  Modal,
  NavLink,
  PasswordInput,
  ScrollArea,
  Stack,
  Table,
  Text,
  Tooltip,
  UnstyledButton,
  useMantineColorScheme,
} from '@mantine/core';
import { useDisclosure, useHotkeys } from '@mantine/hooks';
import { spotlight } from '@mantine/spotlight';
import {
  IconBriefcase,
  IconBuilding,
  IconCalendar,
  IconChartBar,
  IconChecklist,
  IconChevronDown,
  IconFileInvoice,
  IconFileText,
  IconHelp,
  IconKeyboard,
  IconLayoutDashboard,
  IconLogout,
  IconMoon,
  IconPlus,
  IconSearch,
  IconSettings,
  IconSun,
  IconTarget,
  IconUser,
  IconUsers,
} from '@tabler/icons-react';
import { api, notifyError, notifyOk } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { useSettings } from '@/api/hooks';
import { initials } from '@/lib/format';
import { ROLE_LABELS } from '@/lib/labels';
import GlobalSearch from './GlobalSearch';
import NotificationsBell from './NotificationsBell';
import Onboarding from './Onboarding';
import { QuickCreateProvider, useQuickCreate } from './QuickCreate';

const NAV = [
  { to: '/', label: 'Дашборд', icon: IconLayoutDashboard, end: true },
  { to: '/leads', label: 'Лиды', icon: IconTarget },
  { to: '/deals', label: 'Сделки', icon: IconBriefcase, perm: 'deals.view' },
  { to: '/companies', label: 'Компании', icon: IconBuilding },
  { to: '/contacts', label: 'Контакты', icon: IconUsers },
  { to: '/tasks', label: 'Задачи', icon: IconChecklist },
  { to: '/calendar', label: 'Календарь', icon: IconCalendar },
  { to: '/proposals', label: 'Коммерческие предложения', icon: IconFileText, perm: 'proposals.edit' },
  { to: '/finance', label: 'Счета и оплаты', icon: IconFileInvoice, perm: 'finance.view' },
  { to: '/reports', label: 'Отчёты', icon: IconChartBar, perm: 'analytics.view' },
];

const HOTKEYS: [string[], string][] = [
  [['/'], 'Глобальный поиск'],
  [['Ctrl', 'K'], 'Глобальный поиск'],
  [['C'], 'Новая сделка'],
  [['L'], 'Новый лид'],
  [['T'], 'Новая задача'],
  [['N'], 'Новая компания'],
  [['?'], 'Список горячих клавиш'],
  [['Ctrl', 'Enter'], 'Сохранить заметку в ленте'],
];

function ForcePasswordChange() {
  const { user, reload } = useAuth();
  const [current, setCurrent] = useState('');
  const [next, setNext] = useState('');
  const [saving, setSaving] = useState(false);
  if (!user?.must_change_password) return null;
  const save = async () => {
    setSaving(true);
    try {
      await api.post('/auth/me/password', { current_password: current, new_password: next });
      notifyOk('Пароль изменён');
      await reload();
    } catch (e) {
      notifyError(e);
    } finally {
      setSaving(false);
    }
  };
  return (
    <Modal opened onClose={() => undefined} withCloseButton={false} title="Смените временный пароль" closeOnEscape={false}
      closeOnClickOutside={false}>
      <Stack>
        <Text size="sm" c="dimmed">
          Для безопасности задайте собственный пароль: не короче 8 символов, буквы и цифры.
        </Text>
        <PasswordInput label="Текущий (временный) пароль" value={current} onChange={(e) => setCurrent(e.currentTarget.value)} />
        <PasswordInput label="Новый пароль" value={next} onChange={(e) => setNext(e.currentTarget.value)} />
        <Button onClick={save} loading={saving} disabled={!current || next.length < 8}>
          Сохранить
        </Button>
      </Stack>
    </Modal>
  );
}

function Shell() {
  const [opened, { toggle, close }] = useDisclosure();
  const [hotkeysOpen, hotkeys] = useDisclosure(false);
  const { user, logout, can } = useAuth();
  const { colorScheme, toggleColorScheme } = useMantineColorScheme();
  const navigate = useNavigate();
  const location = useLocation();
  const { open } = useQuickCreate();
  const { data: settings } = useSettings();
  const brand = settings?.company_profile?.name?.replace(/^ООО\s*/, '').replace(/[«»"]/g, '') || 'CRM';

  useHotkeys([
    ['c', () => can('deals.edit') && open('deal')],
    ['l', () => can('leads.edit') && open('lead')],
    ['t', () => open('task')],
    ['n', () => can('companies.edit') && open('company')],
    ['shift+/', hotkeys.open],
  ]);

  const nav = NAV.filter((n) => !n.perm || can(n.perm));
  const adminVisible = can('users.manage') || can('dictionaries.edit') || can('pipeline.edit') || can('audit.view') ||
    can('products.edit') || can('templates.edit') || can('marketing.edit');

  return (
    <AppShell header={{ height: 60 }} navbar={{ width: 250, breakpoint: 'md', collapsed: { mobile: !opened } }}
      padding="lg">
      <AppShell.Header>
        <Group h="100%" px="md" justify="space-between" wrap="nowrap">
          <Group gap="sm" wrap="nowrap">
            <Burger opened={opened} onClick={toggle} hiddenFrom="md" size="sm" aria-label="Меню" />
            <UnstyledButton component={Link} to="/">
              <Group gap={8} wrap="nowrap">
                <img src="/favicon.svg" width={30} height={30} alt="" />
                <Text fw={700} size="lg" visibleFrom="xs">
                  {brand}
                </Text>
              </Group>
            </UnstyledButton>
          </Group>
          <UnstyledButton onClick={() => spotlight.open()} data-tour="search" visibleFrom="md"
            style={{ flex: 1, maxWidth: 440, border: '1px solid var(--mantine-color-gray-3)', borderRadius: 8,
              padding: '6px 12px', background: 'var(--mantine-color-body)' }} aria-label="Поиск">
            <Group justify="space-between" wrap="nowrap">
              <Group gap={8} wrap="nowrap">
                <IconSearch size={16} color="var(--mantine-color-dimmed)" />
                <Text size="sm" c="dimmed">
                  Поиск по компаниям, ИНН, телефонам…
                </Text>
              </Group>
              <Kbd size="xs">/</Kbd>
            </Group>
          </UnstyledButton>
          <Group gap={6} wrap="nowrap">
            <ActionIcon hiddenFrom="md" variant="subtle" color="gray" size="lg" onClick={() => spotlight.open()}
              aria-label="Поиск">
              <IconSearch size={20} />
            </ActionIcon>
            <Menu position="bottom-end" shadow="md" width={220}>
              <Menu.Target>
                <Button leftSection={<IconPlus size={16} />} size="sm" data-tour="create" visibleFrom="xs">
                  Создать
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                {can('deals.edit') && (
                  <Menu.Item leftSection={<IconBriefcase size={16} />} rightSection={<Kbd size="xs">C</Kbd>}
                    onClick={() => open('deal')}>
                    Сделку
                  </Menu.Item>
                )}
                {can('leads.edit') && (
                  <Menu.Item leftSection={<IconTarget size={16} />} rightSection={<Kbd size="xs">L</Kbd>}
                    onClick={() => open('lead')}>
                    Лид
                  </Menu.Item>
                )}
                {can('companies.edit') && (
                  <Menu.Item leftSection={<IconBuilding size={16} />} rightSection={<Kbd size="xs">N</Kbd>}
                    onClick={() => open('company')}>
                    Компанию
                  </Menu.Item>
                )}
                <Menu.Item leftSection={<IconChecklist size={16} />} rightSection={<Kbd size="xs">T</Kbd>}
                  onClick={() => open('task')}>
                  Задачу
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
            <Tooltip label="Горячие клавиши (?)">
              <ActionIcon variant="subtle" color="gray" size="lg" onClick={hotkeys.open} visibleFrom="sm"
                aria-label="Горячие клавиши">
                <IconKeyboard size={20} />
              </ActionIcon>
            </Tooltip>
            <div data-tour="bell">
              <NotificationsBell />
            </div>
            <Menu position="bottom-end" shadow="md" width={240}>
              <Menu.Target>
                <UnstyledButton aria-label="Меню пользователя">
                  <Group gap={8} wrap="nowrap">
                    <Avatar color="blue" radius="xl" size={34}>
                      {initials(user?.full_name)}
                    </Avatar>
                    <div style={{ lineHeight: 1.1 }} className="no-print">
                      <Text size="sm" fw={500} visibleFrom="lg">
                        {user?.full_name.split(' ').slice(0, 2).join(' ')}
                      </Text>
                      <Text size="xs" c="dimmed" visibleFrom="lg">
                        {ROLE_LABELS[user?.role ?? '']}
                      </Text>
                    </div>
                    <IconChevronDown size={14} />
                  </Group>
                </UnstyledButton>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Label>{user?.email}</Menu.Label>
                <Menu.Item leftSection={<IconUser size={16} />} onClick={() => navigate('/profile')}>
                  Профиль и уведомления
                </Menu.Item>
                <Menu.Item leftSection={colorScheme === 'dark' ? <IconSun size={16} /> : <IconMoon size={16} />}
                  onClick={toggleColorScheme}>
                  {colorScheme === 'dark' ? 'Светлая тема' : 'Тёмная тема'}
                </Menu.Item>
                <Menu.Item leftSection={<IconHelp size={16} />} onClick={() => navigate('/help')}>
                  Помощь
                </Menu.Item>
                <Menu.Divider />
                <Menu.Item leftSection={<IconLogout size={16} />} color="red" onClick={() => logout()}>
                  Выйти
                </Menu.Item>
              </Menu.Dropdown>
            </Menu>
          </Group>
        </Group>
      </AppShell.Header>

      <AppShell.Navbar p="sm">
        <AppShell.Section grow component={ScrollArea} data-tour="nav">
          {nav.map((n) => (
            <NavLink key={n.to} component={RouterNavLink} to={n.to} end={n.end} label={n.label}
              leftSection={<n.icon size={19} stroke={1.6} />} onClick={close}
              active={n.end ? location.pathname === '/' : location.pathname.startsWith(n.to)}
              style={{ borderRadius: 8 }} />
          ))}
        </AppShell.Section>
        <AppShell.Section>
          {adminVisible && (
            <NavLink component={RouterNavLink} to="/admin" label="Администрирование" onClick={close}
              leftSection={<IconSettings size={19} stroke={1.6} />} active={location.pathname.startsWith('/admin')}
              style={{ borderRadius: 8 }} />
          )}
          <NavLink component={RouterNavLink} to="/help" label="Помощь" onClick={close}
            leftSection={<IconHelp size={19} stroke={1.6} />} style={{ borderRadius: 8 }} />
        </AppShell.Section>
      </AppShell.Navbar>

      <AppShell.Main>
        <Outlet />
      </AppShell.Main>

      <GlobalSearch />
      <Onboarding />
      <ForcePasswordChange />
      <Modal opened={hotkeysOpen} onClose={hotkeys.close} title="Горячие клавиши">
        <Table>
          <Table.Tbody>
            {HOTKEYS.map(([keys, label]) => (
              <Table.Tr key={label + keys.join()}>
                <Table.Td>
                  {keys.map((k, i) => (
                    <span key={k}>
                      {i > 0 && ' + '}
                      <Kbd>{k}</Kbd>
                    </span>
                  ))}
                </Table.Td>
                <Table.Td>{label}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Modal>
    </AppShell>
  );
}

export default function AppLayout() {
  return (
    <QuickCreateProvider>
      <Shell />
    </QuickCreateProvider>
  );
}
