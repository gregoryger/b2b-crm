import { useState } from 'react';
import { Alert, Badge, Button, Card, Grid, Group, Modal, PasswordInput, PinInput, SimpleGrid, Stack, Switch, Text, TextInput, Title } from '@mantine/core';
import { QRCodeSVG } from 'qrcode.react';
import { IconBrandTelegram, IconShieldCheck } from '@tabler/icons-react';
import { api, notifyError, notifyOk } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/ui';
import { ROLE_LABELS } from '@/lib/labels';

export default function ProfilePage() {
  const { user, reload } = useAuth();
  const [name, setName] = useState(user?.full_name ?? '');
  const [position, setPosition] = useState(user?.position ?? '');
  const [phone, setPhone] = useState(user?.phone ?? '');
  const [cur, setCur] = useState('');
  const [next, setNext] = useState('');
  const [totp, setTotp] = useState<{ secret: string; otpauth_url: string } | null>(null);
  const [disable2fa, setDisable2fa] = useState(false);
  const [code, setCode] = useState('');
  if (!user) return null;

  const patch = async (body: object, msg = 'Сохранено') => {
    try {
      await api.patch('/auth/me', body);
      notifyOk(msg);
      reload();
    } catch (e) {
      notifyError(e);
    }
  };
  const changePassword = async () => {
    try {
      await api.post('/auth/me/password', { current_password: cur, new_password: next });
      notifyOk('Пароль изменён');
      setCur('');
      setNext('');
    } catch (e) {
      notifyError(e);
    }
  };
  const setup2fa = async () => {
    try {
      const { data } = await api.post('/auth/me/2fa/setup');
      setTotp(data);
    } catch (e) {
      notifyError(e);
    }
  };
  const enable2fa = async (c: string) => {
    try {
      await api.post('/auth/me/2fa/enable', { code: c });
      notifyOk('Двухфакторная аутентификация включена');
      setTotp(null);
      setCode('');
      reload();
    } catch (e) {
      notifyError(e);
      setCode('');
    }
  };
  const off2fa = async (c: string) => {
    try {
      await api.post('/auth/me/2fa/disable', { code: c });
      notifyOk('2FA отключена');
      setDisable2fa(false);
      setCode('');
      reload();
    } catch (e) {
      notifyError(e);
      setCode('');
    }
  };
  const telegram = async () => {
    try {
      const { data } = await api.post('/auth/me/telegram');
      if (data.url) window.open(data.url, '_blank');
      else notifyOk(`Отправьте боту команду /start ${data.code}`);
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <>
      <PageHeader title="Профиль" subtitle={`${user.email} · ${ROLE_LABELS[user.role]}`} />
      <Grid>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Stack>
            <Card>
              <Title order={5} mb="md">Личные данные</Title>
              <Stack>
                <TextInput label="ФИО" value={name} onChange={(e) => setName(e.currentTarget.value)} />
                <SimpleGrid cols={2}>
                  <TextInput label="Должность" value={position} onChange={(e) => setPosition(e.currentTarget.value)} />
                  <TextInput label="Телефон" value={phone} onChange={(e) => setPhone(e.currentTarget.value)} />
                </SimpleGrid>
                <Text size="xs" c="dimmed">Должность и телефон подставляются в коммерческие предложения и письма.</Text>
                <Group justify="flex-end"><Button onClick={() => patch({ full_name: name, position, phone })}>Сохранить</Button></Group>
              </Stack>
            </Card>
            <Card>
              <Title order={5} mb="md">Смена пароля</Title>
              <Stack>
                <PasswordInput label="Текущий пароль" value={cur} onChange={(e) => setCur(e.currentTarget.value)} />
                <PasswordInput label="Новый пароль" description="Не короче 8 символов, буквы и цифры" value={next} onChange={(e) => setNext(e.currentTarget.value)} />
                <Group justify="flex-end"><Button onClick={changePassword} disabled={!cur || next.length < 8}>Изменить пароль</Button></Group>
              </Stack>
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 6 }}>
          <Stack>
            <Card>
              <Title order={5} mb="md">Уведомления</Title>
              <Stack>
                <Switch label="В интерфейсе CRM" description="Колокольчик и всплывающие уведомления" checked={user.notify_push}
                  onChange={(e) => patch({ notify_push: e.currentTarget.checked })} />
                <Switch label="По email" description={user.email} checked={user.notify_email}
                  onChange={(e) => patch({ notify_email: e.currentTarget.checked })} />
                <Group justify="space-between" align="flex-start">
                  <Switch label="В Telegram" description={user.telegram_linked ? 'Бот подключён' : 'Сначала подключите бота'}
                    checked={user.notify_telegram} disabled={!user.telegram_linked}
                    onChange={(e) => patch({ notify_telegram: e.currentTarget.checked })} />
                  {user.telegram_linked ? (
                    <Button size="xs" variant="subtle" color="red" onClick={async () => { await api.delete('/auth/me/telegram'); reload(); }}>Отключить</Button>
                  ) : (
                    <Button size="xs" variant="light" leftSection={<IconBrandTelegram size={14} />} onClick={telegram}>Подключить бота</Button>
                  )}
                </Group>
                <Text size="xs" c="dimmed">Напоминания о задачах приходят за 15 минут, час или день — как указано в задаче.</Text>
              </Stack>
            </Card>
            <Card>
              <Group justify="space-between" mb="md">
                <Title order={5}>Двухфакторная аутентификация</Title>
                {user.totp_enabled ? <Badge color="teal" leftSection={<IconShieldCheck size={12} />}>Включена</Badge> : <Badge color="gray">Выключена</Badge>}
              </Group>
              <Text size="sm" c="dimmed" mb="md">
                При входе дополнительно запрашивается код из приложения (Яндекс Ключ, Google Authenticator и др.).
              </Text>
              {user.totp_enabled ? (
                <Button variant="light" color="red" onClick={() => setDisable2fa(true)}>Отключить 2FA</Button>
              ) : (
                <Button variant="light" onClick={setup2fa}>Включить 2FA</Button>
              )}
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      <Modal opened={!!totp} onClose={() => setTotp(null)} title="Подключение 2FA">
        {totp && (
          <Stack align="center">
            <Text size="sm">1. Отсканируйте QR-код в приложении-аутентификаторе</Text>
            <QRCodeSVG value={totp.otpauth_url} size={180} />
            <Text size="xs" c="dimmed">или введите ключ вручную: <b>{totp.secret}</b></Text>
            <Text size="sm">2. Введите 6-значный код из приложения</Text>
            <PinInput length={6} type="number" value={code} onChange={setCode} onComplete={enable2fa} oneTimeCode />
          </Stack>
        )}
      </Modal>
      <Modal opened={disable2fa} onClose={() => setDisable2fa(false)} title="Отключение 2FA">
        <Stack align="center">
          <Alert color="orange" w="100%">Для подтверждения введите текущий код из приложения</Alert>
          <PinInput length={6} type="number" value={code} onChange={setCode} onComplete={off2fa} oneTimeCode />
        </Stack>
      </Modal>
    </>
  );
}
