import { useState } from 'react';
import { Alert, Badge, Button, Card, Code, CopyButton, Group, Modal, SimpleGrid, Stack, Table, Text, TextInput, ThemeIcon, Title } from '@mantine/core';
import { IconApi, IconBrandTelegram, IconDatabaseExport, IconMail, IconPhone, IconPlus, IconWorldWww } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError } from '@/api/client';
import { useApi } from '@/api/hooks';
import { dateTime } from '@/lib/format';
import { QueryFeedback } from '@/components/ui';

interface ApiKey { id: number; name: string; prefix: string; is_active: boolean; created_at: string; last_used_at: string | null }

const STATUS: Record<string, { label: string; color: string }> = {
  demo: { label: 'Демо-режим', color: 'orange' },
  configured: { label: 'Настроено', color: 'blue' },
  not_configured: { label: 'Не настроено', color: 'gray' },
  disabled: { label: 'Выключено', color: 'gray' },
};

function ConnectionStatus({ value }: { value?: string }) {
  const state = STATUS[value ?? ''] ?? { label: 'Нет данных о настройке', color: 'gray' };
  return <Badge color={state.color}>{state.label}</Badge>;
}

const origin = window.location.origin;
const FORM_SNIPPET = (key: string) => `<form id="crm-lead-form">
  <input name="name" placeholder="Ваше имя" required>
  <input name="company" placeholder="Компания">
  <input name="phone" placeholder="Телефон" required>
  <input name="email" type="email" placeholder="Email">
  <textarea name="message" placeholder="Сообщение"></textarea>
  <button type="submit">Отправить</button>
</form>
<script>
document.getElementById('crm-lead-form').addEventListener('submit', async (e) => {
  e.preventDefault();
  const data = Object.fromEntries(new FormData(e.target));
  const utm = new URLSearchParams(location.search);
  ['utm_source', 'utm_medium', 'utm_campaign'].forEach((k) => utm.get(k) && (data[k] = utm.get(k)));
  const r = await fetch('${origin}/api/v1/public/leads', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json', 'X-Api-Key': '${key}' },
    body: JSON.stringify(data),
  });
  e.target.innerHTML = r.ok ? 'Спасибо! Мы свяжемся с вами.' : 'Ошибка отправки';
});
</script>`;

function Integration({ icon, title, status, children }: { icon: React.ReactNode; title: string; status: React.ReactNode; children: React.ReactNode }) {
  return (
    <Card>
      <Group justify="space-between" mb="sm">
        <Group gap="sm"><ThemeIcon variant="light" size="lg">{icon}</ThemeIcon><Title order={5}>{title}</Title></Group>
        {status}
      </Group>
      <Text size="sm" c="dimmed" component="div">{children}</Text>
    </Card>
  );
}

export default function IntegrationsAdmin() {
  const qc = useQueryClient();
  const { data: keys } = useApi<ApiKey[]>(['api-keys'], '/api-keys');
  const statusQuery = useApi<{ smtp: string; imap: string; telephony: string; telegram: string; rate_limit: number }>(
    ['integration-status'], '/integrations/status');
  const status = statusQuery.data;
  const [name, setName] = useState('');
  const [created, setCreated] = useState<string | null>(null);
  const create = async () => {
    try {
      const { data } = await api.post('/api-keys', null, { params: { name } });
      setCreated(data.key);
      setName('');
      qc.invalidateQueries({ queryKey: ['api-keys'] });
    } catch (e) {
      notifyError(e);
    }
  };
  const revoke = async (id: number) => {
    await api.delete(`/api-keys/${id}`).catch(notifyError);
    qc.invalidateQueries({ queryKey: ['api-keys'] });
  };
  return (
    <Stack>
      <QueryFeedback query={statusQuery} hasData={!!status} />
      <Text size="sm" c="dimmed">Статусы отражают настройки подключения. Доставку писем, уведомлений и звонков проверяют пробной отправкой.</Text>
      <Card>
        <Group gap="sm" mb="sm"><ThemeIcon variant="light" size="lg"><IconWorldWww /></ThemeIcon><Title order={5}>Сайт и лендинги: приём заявок</Title></Group>
        <Text size="sm" c="dimmed" mb="md">
          Заявки с веб-форм отправляются на <Code>POST {origin}/api/v1/public/leads</Code> с заголовком <Code>X-Api-Key</Code>
          и автоматически распределяются между менеджерами. Создайте отдельный ключ для каждого сайта.
        </Text>
        <Table mb="md">
          <Table.Thead><Table.Tr><Table.Th>Название</Table.Th><Table.Th>Ключ</Table.Th><Table.Th>Последнее использование</Table.Th><Table.Th /></Table.Tr></Table.Thead>
          <Table.Tbody>
            {keys?.map((k) => (
              <Table.Tr key={k.id} opacity={k.is_active ? 1 : 0.5}>
                <Table.Td>{k.name}</Table.Td>
                <Table.Td><Code>{k.prefix}…</Code></Table.Td>
                <Table.Td>{k.last_used_at ? dateTime(k.last_used_at) : '—'}</Table.Td>
                <Table.Td>{k.is_active ? <Button size="xs" variant="subtle" color="red" onClick={() => revoke(k.id)}>Отозвать</Button> : <Badge color="gray">Отозван</Badge>}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group>
          <TextInput placeholder="Например: Лендинг «Серверы»" value={name} onChange={(e) => setName(e.currentTarget.value)} w={320} aria-label="Название ключа" />
          <Button leftSection={<IconPlus size={16} />} onClick={create} disabled={!name.trim()}>Создать ключ</Button>
        </Group>
      </Card>
      <SimpleGrid cols={{ base: 1, md: 2 }}>
        <Integration icon={<IconMail />} title="Почта (SMTP / IMAP)" status={<ConnectionStatus value={status?.smtp} />}>
          <Group mb="xs"><Text size="sm">Входящая почта IMAP:</Text><ConnectionStatus value={status?.imap} /></Group>
          {status?.smtp === 'demo' && <Text size="sm" c="orange" mb="xs">Письма попадают в тестовый почтовый ящик. Реальным получателям они не доставляются.</Text>}
          Письма уходят через SMTP с отслеживанием открытий (пиксель). Входящие письма забираются по IMAP каждые 2 минуты:
          письма от известных контактов попадают в ленту клиента, от новых адресатов — создают лиды (email-парсер).
          Параметры задаются в <Code>.env</Code>: SMTP_*, IMAP_*.
        </Integration>
        <Integration icon={<IconPhone />} title="Телефония (SIP-АТС)" status={<ConnectionStatus value={status?.telephony} />}>
          {status?.telephony === 'demo' && <Text size="sm" c="orange" mb="xs">Демонстрация: событие сохраняется в CRM без реального звонка.</Text>}
          События звонков АТС отправляет на <Code>{origin}/api/v1/integrations/telephony/events</Code> (заголовок <Code>X-Webhook-Secret</Code>).
          Входящий звонок показывает менеджеру карточку клиента, завершённый — сохраняется в ленте с записью разговора,
          звонок с неизвестного номера создаёт лид. Click-to-call — кнопка рядом с любым телефоном.
          Внутренние номера сотрудников задаются в разделе «Пользователи».
        </Integration>
        <Integration icon={<IconBrandTelegram />} title="Telegram-бот" status={<ConnectionStatus value={status?.telegram} />}>
          Напоминания о задачах и уведомления о лидах в Telegram. Сотрудник подключает бота в своём профиле одной кнопкой.
          Токен бота (от @BotFather) задаётся в <Code>.env</Code>.
        </Integration>
        <Integration icon={<IconDatabaseExport />} title="1С: Бухгалтерия" status={<Badge color="blue">XML-выгрузка</Badge>}>
          Счета, акты и контрагенты выгружаются в XML в разделе «Счета и оплаты → Выгрузка в 1С». Выгруженные документы
          помечаются, повторно не выгружаются.
          Для загрузки файла нужна обработка в конфигурации 1С заказчика.
        </Integration>
        <Integration icon={<IconApi />} title="REST API" status={<Badge color="teal">OpenAPI 3</Badge>}>
          Полная документация API для интеграции с другими системами: <a href="/api/docs" target="_blank" className="link">/api/docs</a>.
          Аутентификация JWT{status ? `, лимит ${status.rate_limit} запросов в минуту на пользователя` : ''}.
        </Integration>
      </SimpleGrid>
      <Modal opened={!!created} onClose={() => setCreated(null)} title="API-ключ создан" size="xl">
        <Stack>
          <Alert color="orange">Скопируйте ключ сейчас — после закрытия окна он больше не будет показан.</Alert>
          <Group><Code fz="md">{created}</Code>
            <CopyButton value={created ?? ''}>{({ copied, copy }) => <Button size="xs" onClick={copy}>{copied ? 'Скопирован' : 'Копировать'}</Button>}</CopyButton>
          </Group>
          <Text size="sm" fw={500}>Пример формы для сайта:</Text>
          <Code block style={{ maxHeight: 300, overflow: 'auto' }}>{FORM_SNIPPET(created ?? '')}</Code>
        </Stack>
      </Modal>
    </Stack>
  );
}
