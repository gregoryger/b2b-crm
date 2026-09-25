import { useEffect, useRef } from 'react';
import { useNavigate } from 'react-router-dom';
import { ActionIcon, Button, Divider, Group, Indicator, Popover, ScrollArea, Stack, Text, UnstyledButton } from '@mantine/core';
import { notifications } from '@mantine/notifications';
import { IconBell } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Notification } from '@/api/types';
import { ago } from '@/lib/format';

/** Push-уведомления в интерфейсе: опрос каждые 30 секунд, всплывающие уведомления о новых событиях */
export default function NotificationsBell() {
  const qc = useQueryClient();
  const navigate = useNavigate();
  const lastSeen = useRef<number | null>(null);
  const { data: counter } = useApi<{ count: number; latest_id: number | null }>(['notif-count'],
    '/notifications/unread-count', undefined, { refetchInterval: 30_000, refetchOnWindowFocus: true });
  const { data: list, refetch } = useApi<Notification[]>(['notifications'], '/notifications', { limit: 20 });

  useEffect(() => {
    if (!counter?.latest_id) return;
    if (lastSeen.current !== null && counter.latest_id > lastSeen.current) {
      api.get<Notification[]>('/notifications', { params: { unread: true, limit: 5 } }).then(({ data }) => {
        data.filter((n) => n.id > (lastSeen.current ?? 0)).reverse().forEach((n) => {
          notifications.show({
            title: n.title, message: n.body || '', color: 'blue', autoClose: 8000,
            onClick: () => n.link && navigate(n.link), style: { cursor: n.link ? 'pointer' : undefined },
          });
          if ('Notification' in window && Notification.permission === 'granted' && document.hidden) {
            new Notification(n.title, { body: n.body || '', icon: '/favicon.svg' });
          }
        });
        refetch();
      });
    }
    lastSeen.current = Math.max(lastSeen.current ?? 0, counter.latest_id);
  }, [counter, navigate, refetch]);

  const markAll = async () => {
    await api.post('/notifications/read', []);
    qc.invalidateQueries({ queryKey: ['notif-count'] });
    qc.invalidateQueries({ queryKey: ['notifications'] });
  };

  const open = async (n: Notification) => {
    if (!n.is_read) {
      await api.post('/notifications/read', [n.id]);
      qc.invalidateQueries({ queryKey: ['notif-count'] });
      qc.invalidateQueries({ queryKey: ['notifications'] });
    }
    if (n.link) navigate(n.link);
  };

  return (
    <Popover width={380} position="bottom-end" shadow="md" onOpen={() => {
      refetch();
      if ('Notification' in window && Notification.permission === 'default') Notification.requestPermission();
    }}>
      <Popover.Target>
        <Indicator label={counter?.count} size={16} disabled={!counter?.count} offset={4} color="red">
          <ActionIcon variant="subtle" color="gray" size="lg" aria-label="Уведомления">
            <IconBell size={20} />
          </ActionIcon>
        </Indicator>
      </Popover.Target>
      <Popover.Dropdown p={0}>
        <Group justify="space-between" px="md" py="sm">
          <Text fw={600}>Уведомления</Text>
          {!!counter?.count && (
            <Button variant="subtle" size="compact-xs" onClick={markAll}>
              Прочитать все
            </Button>
          )}
        </Group>
        <Divider />
        <ScrollArea.Autosize mah={420}>
          {!list?.length && (
            <Text c="dimmed" size="sm" p="md">
              Уведомлений нет
            </Text>
          )}
          <Stack gap={0}>
            {list?.map((n) => (
              <UnstyledButton key={n.id} onClick={() => open(n)} px="md" py="sm"
                style={{ borderBottom: '1px solid var(--mantine-color-gray-2)',
                  background: n.is_read ? undefined : 'var(--mantine-color-blue-0)' }}>
                <Text size="sm" fw={n.is_read ? 400 : 600}>
                  {n.title}
                </Text>
                {n.body && (
                  <Text size="xs" c="dimmed" lineClamp={2}>
                    {n.body}
                  </Text>
                )}
                <Text size="xs" c="dimmed" mt={2}>
                  {ago(n.created_at)}
                </Text>
              </UnstyledButton>
            ))}
          </Stack>
        </ScrollArea.Autosize>
      </Popover.Dropdown>
    </Popover>
  );
}
