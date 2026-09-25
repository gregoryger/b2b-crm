import { ReactNode } from 'react';
import { Link } from 'react-router-dom';
import {
  ActionIcon,
  Badge,
  Box,
  Card,
  Center,
  Group,
  Pagination,
  Paper,
  Select,
  Stack,
  Text,
  ThemeIcon,
  Title,
  Tooltip,
} from '@mantine/core';
import { IconArrowDownRight, IconArrowUpRight, IconInbox, IconPhoneCall } from '@tabler/icons-react';
import { api, notifyError, notifyOk } from '@/api/client';
import { num } from '@/lib/format';

export function PageHeader({ title, subtitle, actions, back }: {
  title: ReactNode; subtitle?: ReactNode; actions?: ReactNode; back?: ReactNode;
}) {
  return (
    <Group justify="space-between" align="flex-start" mb="lg" wrap="wrap" gap="sm">
      <Box style={{ minWidth: 0, flex: 1 }}>
        {back}
        <Title order={2} style={{ wordBreak: 'break-word' }}>
          {title}
        </Title>
        {subtitle && (
          <Text c="dimmed" size="sm" mt={4} component="div">
            {subtitle}
          </Text>
        )}
      </Box>
      {actions && <Group gap="xs">{actions}</Group>}
    </Group>
  );
}

export function StatusBadge({ map, value, size = 'sm' }: {
  map: Record<string, { label: string; color: string }>; value: string | null | undefined; size?: string;
}) {
  if (!value) return null;
  const item = map[value] ?? { label: value, color: 'gray' };
  return (
    <Badge color={item.color} size={size}>
      {item.label}
    </Badge>
  );
}

export function EntityLink({ to, children }: { to: string; children: ReactNode }) {
  return (
    <Link to={to} className="link" onClick={(e) => e.stopPropagation()}>
      {children}
    </Link>
  );
}

export function Empty({ text = 'Пока ничего нет', action }: { text?: string; action?: ReactNode }) {
  return (
    <Center py="xl">
      <Stack align="center" gap="xs">
        <ThemeIcon size={48} radius="xl" variant="light" color="gray">
          <IconInbox size={26} />
        </ThemeIcon>
        <Text c="dimmed" size="sm">
          {text}
        </Text>
        {action}
      </Stack>
    </Center>
  );
}

export function StatCard({ label, value, hint, diff, icon, color = 'blue' }: {
  label: string; value: ReactNode; hint?: ReactNode; diff?: number | null; icon?: ReactNode; color?: string;
}) {
  return (
    <Card padding="md">
      <Group justify="space-between" align="flex-start" wrap="nowrap">
        <div>
          <Text size="xs" c="dimmed" tt="uppercase" fw={600}>
            {label}
          </Text>
          <Text fz={24} fw={700} mt={4} lh={1.2}>
            {value}
          </Text>
        </div>
        {icon && (
          <ThemeIcon variant="light" color={color} size={38} radius="md">
            {icon}
          </ThemeIcon>
        )}
      </Group>
      <Group gap={6} mt={6}>
        {diff !== undefined && diff !== null && Number.isFinite(diff) && (
          <Text size="xs" fw={600} className={diff >= 0 ? 'stat-diff-up' : 'stat-diff-down'}
            style={{ display: 'flex', alignItems: 'center' }}>
            {diff >= 0 ? <IconArrowUpRight size={14} /> : <IconArrowDownRight size={14} />}
            {num(Math.abs(diff), 0)}%
          </Text>
        )}
        {hint && (
          <Text size="xs" c="dimmed">
            {hint}
          </Text>
        )}
      </Group>
    </Card>
  );
}

export function Pager({ page, pages, total, pageSize, onPage, onPageSize }: {
  page: number; pages: number; total: number; pageSize: number; onPage: (p: number) => void;
  onPageSize?: (s: number) => void;
}) {
  if (!total) return null;
  return (
    <Group justify="space-between" mt="md">
      <Text size="sm" c="dimmed">
        Всего: {num(total)}
      </Text>
      <Group gap="sm">
        {onPageSize && (
          <Select size="xs" w={90} data={['25', '50', '100']} value={String(pageSize)}
            onChange={(v) => onPageSize(Number(v))} aria-label="Записей на странице" allowDeselect={false} />
        )}
        {pages > 1 && <Pagination size="sm" total={pages} value={page} onChange={onPage} />}
      </Group>
    </Group>
  );
}

export function Section({ title, actions, children, p = 'lg' }: {
  title?: ReactNode; actions?: ReactNode; children: ReactNode; p?: string;
}) {
  return (
    <Paper withBorder p={p}>
      {(title || actions) && (
        <Group justify="space-between" mb="md">
          {typeof title === 'string' ? <Title order={4}>{title}</Title> : title}
          {actions}
        </Group>
      )}
      {children}
    </Paper>
  );
}

export function Field({ label, children }: { label: string; children: ReactNode }) {
  return (
    <div>
      <Text size="xs" c="dimmed">
        {label}
      </Text>
      <Text size="sm" component="div" style={{ wordBreak: 'break-word' }}>
        {children || '—'}
      </Text>
    </div>
  );
}

/** Телефон с кнопкой звонка через АТС (click-to-call) */
export function Phone({ phone, links }: { phone: string | null | undefined; links?: Record<string, number | null | undefined> }) {
  if (!phone) return <>—</>;
  const call = async () => {
    try {
      await api.post('/telephony/call', { phone, ...links });
      notifyOk(`АТС соединяет вас с ${phone}`, 'Звонок');
    } catch (e) {
      notifyError(e, 'Не удалось позвонить');
    }
  };
  return (
    <Group gap={4} wrap="nowrap" component="span">
      <a href={`tel:${phone.replace(/[^\d+]/g, '')}`} className="link">
        {phone}
      </a>
      <Tooltip label="Позвонить через АТС">
        <ActionIcon size="sm" variant="subtle" color="teal" onClick={call} aria-label="Позвонить">
          <IconPhoneCall size={14} />
        </ActionIcon>
      </Tooltip>
    </Group>
  );
}
