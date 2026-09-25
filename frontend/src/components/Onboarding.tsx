import { useEffect, useLayoutEffect, useState } from 'react';
import { Box, Button, Group, Kbd, Paper, Portal, Progress, Text, Title } from '@mantine/core';
import { api } from '@/api/client';
import { useAuth } from '@/auth/AuthContext';

interface Step {
  target?: string;
  title: string;
  text: React.ReactNode;
}

const STEPS: Step[] = [
  {
    title: 'Добро пожаловать в CRM 👋',
    text: 'Покажем основные разделы — это займёт меньше минуты. Подсказки можно перезапустить в разделе «Помощь».',
  },
  { target: '[data-tour="nav"]', title: 'Разделы системы', text: 'Лиды, клиенты, сделки, задачи, КП, финансы и отчёты. Доступные разделы зависят от вашей роли.' },
  {
    target: '[data-tour="search"]', title: 'Глобальный поиск',
    text: <>Ищите по названию, ИНН, телефону или ФИО. Горячая клавиша — <Kbd>/</Kbd> или <Kbd>Ctrl</Kbd>+<Kbd>K</Kbd>.</>,
  },
  {
    target: '[data-tour="create"]', title: 'Быстрое создание',
    text: <>Новая сделка — <Kbd>C</Kbd>, лид — <Kbd>L</Kbd>, задача — <Kbd>T</Kbd>. Полный список: <Kbd>?</Kbd></>,
  },
  { target: '[data-tour="bell"]', title: 'Уведомления', text: 'Новые лиды, напоминания о задачах, открытие КП клиентом — всё появится здесь. Можно подключить email и Telegram в профиле.' },
  { target: '[data-tour="dashboard"]', title: 'Ваш дашборд', text: 'Задачи на сегодня, ключевые показатели и последние события. Удачной работы!' },
];

function useRect(selector?: string, step?: number) {
  const [rect, setRect] = useState<DOMRect | null>(null);
  useLayoutEffect(() => {
    if (!selector) return setRect(null);
    const update = () => {
      const el = document.querySelector(selector);
      setRect(el ? el.getBoundingClientRect() : null);
    };
    update();
    window.addEventListener('resize', update);
    return () => window.removeEventListener('resize', update);
  }, [selector, step]);
  return rect;
}

export default function Onboarding({ forceOpen, onClose }: { forceOpen?: boolean; onClose?: () => void }) {
  const { user, reload } = useAuth();
  const [open, setOpen] = useState(false);
  const [step, setStep] = useState(0);
  useEffect(() => {
    if (forceOpen) {
      setStep(0);
      setOpen(true);
    } else if (user && !user.onboarding_done && !user.must_change_password) {
      const t = setTimeout(() => setOpen(true), 800);
      return () => clearTimeout(t);
    }
  }, [user, forceOpen]);
  const s = STEPS[step];
  const rect = useRect(s?.target, step);
  if (!open || !s) return null;

  const finish = async () => {
    setOpen(false);
    onClose?.();
    if (!user?.onboarding_done) {
      await api.patch('/auth/me', { onboarding_done: true }).catch(() => undefined);
      reload();
    }
  };

  const pad = 6;
  const cardW = 340;
  let cardStyle: React.CSSProperties = { top: '50%', left: '50%', transform: 'translate(-50%, -50%)' };
  if (rect) {
    const below = rect.bottom + 12 + 180 < window.innerHeight;
    const left = Math.min(Math.max(rect.left, 12), window.innerWidth - cardW - 12);
    cardStyle = rect.width < 320 && rect.left < 300
      ? { top: Math.max(12, Math.min(rect.top, window.innerHeight - 220)), left: rect.right + 16 }
      : below ? { top: rect.bottom + 12, left } : { top: Math.max(12, rect.top - 190), left };
  }

  return (
    <Portal>
      <Box style={{ position: 'fixed', inset: 0, zIndex: 400 }} onClick={finish}>
        {rect ? (
          <Box style={{
            position: 'fixed', top: rect.top - pad, left: rect.left - pad, width: rect.width + pad * 2,
            height: rect.height + pad * 2, borderRadius: 10, boxShadow: '0 0 0 9999px rgba(0,0,0,0.45)',
            outline: '3px solid var(--mantine-color-blue-4)', transition: 'all 200ms', pointerEvents: 'none',
          }} />
        ) : (
          <Box style={{ position: 'fixed', inset: 0, background: 'rgba(0,0,0,0.45)' }} />
        )}
      </Box>
      <Paper shadow="xl" p="lg" w={cardW} style={{ position: 'fixed', zIndex: 401, ...cardStyle }} withBorder
        role="dialog" aria-label={s.title}>
        <Progress value={((step + 1) / STEPS.length) * 100} size="xs" mb="md" />
        <Title order={4}>{s.title}</Title>
        <Text size="sm" mt="xs" c="dimmed">
          {s.text}
        </Text>
        <Group justify="space-between" mt="lg">
          <Button variant="subtle" size="xs" color="gray" onClick={finish}>
            Пропустить
          </Button>
          <Group gap="xs">
            {step > 0 && (
              <Button variant="default" size="xs" onClick={() => setStep(step - 1)}>
                Назад
              </Button>
            )}
            <Button size="xs" onClick={() => (step === STEPS.length - 1 ? finish() : setStep(step + 1))} autoFocus>
              {step === STEPS.length - 1 ? 'Начать работу' : 'Далее'}
            </Button>
          </Group>
        </Group>
      </Paper>
    </Portal>
  );
}
