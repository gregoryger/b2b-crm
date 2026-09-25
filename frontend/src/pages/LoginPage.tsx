import { useState } from 'react';
import { Navigate, useLocation, useNavigate } from 'react-router-dom';
import {
  Alert,
  Anchor,
  Box,
  Button,
  Center,
  Group,
  Paper,
  PasswordInput,
  PinInput,
  SimpleGrid,
  Stack,
  Text,
  TextInput,
  ThemeIcon,
  Title,
} from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconAlertCircle, IconChartFunnel, IconLock, IconShieldCheck, IconUsers } from '@tabler/icons-react';
import { useAuth } from '@/auth/AuthContext';
import { errorMessage } from '@/api/client';

const DEMO = [
  { email: 'head@demo.ru', label: 'Руководитель' },
  { email: 'petrov@demo.ru', label: 'Менеджер' },
  { email: 'marketer@demo.ru', label: 'Маркетолог' },
  { email: 'admin@demo.ru', label: 'Администратор' },
];

export default function LoginPage() {
  const { user, login, verify2fa } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(false);
  const [twoFaToken, setTwoFaToken] = useState<string | null>(null);
  const [code, setCode] = useState('');
  const form = useForm({
    initialValues: { email: '', password: '' },
    validate: {
      email: (v: string) => (/^\S+@\S+$/.test(v) ? null : 'Введите email'),
      password: (v: string) => (v.length ? null : 'Введите пароль'),
    },
  });

  const from = (location.state as { from?: Location })?.from?.pathname || '/';
  if (user) return <Navigate to={from} replace />;

  const submit = form.onSubmit(async (values) => {
    setError(null);
    setLoading(true);
    try {
      const res = await login(values.email.trim().toLowerCase(), values.password);
      if (res.twoFactorToken) setTwoFaToken(res.twoFactorToken);
      else navigate(from, { replace: true });
    } catch (e) {
      setError(errorMessage(e));
    } finally {
      setLoading(false);
    }
  });

  const submit2fa = async (value: string) => {
    if (!twoFaToken) return;
    setLoading(true);
    setError(null);
    try {
      await verify2fa(twoFaToken, value);
      navigate(from, { replace: true });
    } catch (e) {
      setError(errorMessage(e));
      setCode('');
    } finally {
      setLoading(false);
    }
  };

  return (
    <SimpleGrid cols={{ base: 1, md: 2 }} spacing={0} mih="100vh">
      <Box
        visibleFrom="md"
        p={48}
        style={{
          background: 'linear-gradient(135deg, var(--mantine-color-blue-8), var(--mantine-color-indigo-9))',
          color: 'white',
          display: 'flex',
          flexDirection: 'column',
          justifyContent: 'center',
        }}
      >
        <Stack maw={460} gap="xl">
          <Title order={1} c="white">
            CRM для B2B-продаж
          </Title>
          <Text size="lg" opacity={0.9}>
            Клиенты, сделки, коммерческие предложения и аналитика отдела продаж в одной системе.
          </Text>
          {[
            { icon: IconChartFunnel, text: 'Воронка продаж с прогнозом выручки и контролем каждой сделки' },
            { icon: IconUsers, text: 'Единая база компаний и контактов с историей всех взаимодействий' },
            { icon: IconShieldCheck, text: 'Разграничение прав, журнал аудита, шифрование персональных данных' },
          ].map((f) => (
            <Group key={f.text} wrap="nowrap" align="flex-start">
              <ThemeIcon size={36} radius="md" variant="white" color="blue">
                <f.icon size={20} />
              </ThemeIcon>
              <Text opacity={0.95}>{f.text}</Text>
            </Group>
          ))}
        </Stack>
      </Box>
      <Center p="xl">
        <Paper w="100%" maw={400} p="xl" withBorder shadow="sm">
          {!twoFaToken ? (
            <form onSubmit={submit}>
              <Stack>
                <div>
                  <Title order={2}>Вход в систему</Title>
                  <Text c="dimmed" size="sm">
                    Используйте корпоративный email
                  </Text>
                </div>
                {error && (
                  <Alert color="red" icon={<IconAlertCircle size={18} />}>
                    {error}
                  </Alert>
                )}
                <TextInput label="Email" placeholder="name@company.ru" autoComplete="username" autoFocus
                  {...form.getInputProps('email')} />
                <PasswordInput label="Пароль" autoComplete="current-password" {...form.getInputProps('password')} />
                <Button type="submit" loading={loading} fullWidth size="md">
                  Войти
                </Button>
                <Box mt="xs">
                  <Text size="xs" c="dimmed" mb={6}>
                    Демо-доступ (пароль demo12345):
                  </Text>
                  <Group gap={6}>
                    {DEMO.map((d) => (
                      <Anchor key={d.email} size="xs" component="button" type="button"
                        onClick={() => form.setValues({ email: d.email, password: 'demo12345' })}>
                        {d.label}
                      </Anchor>
                    ))}
                  </Group>
                </Box>
              </Stack>
            </form>
          ) : (
            <Stack align="center">
              <ThemeIcon size={48} radius="xl" variant="light">
                <IconLock />
              </ThemeIcon>
              <Title order={3}>Двухфакторная аутентификация</Title>
              <Text c="dimmed" size="sm" ta="center">
                Введите 6-значный код из приложения-аутентификатора
              </Text>
              {error && (
                <Alert color="red" w="100%">
                  {error}
                </Alert>
              )}
              <PinInput length={6} type="number" oneTimeCode autoFocus value={code} onChange={setCode}
                onComplete={submit2fa} disabled={loading} />
              <Anchor size="sm" onClick={() => setTwoFaToken(null)}>
                Назад
              </Anchor>
            </Stack>
          )}
        </Paper>
      </Center>
    </SimpleGrid>
  );
}
