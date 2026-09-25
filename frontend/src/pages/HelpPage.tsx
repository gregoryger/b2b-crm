import { useState } from 'react';
import { Accordion, Anchor, Button, Card, Grid, Group, Kbd, List, Stack, Text, ThemeIcon, Title } from '@mantine/core';
import { IconBook, IconPlayerPlay, IconRoute } from '@tabler/icons-react';
import Onboarding from '@/components/Onboarding';
import { PageHeader } from '@/components/ui';

const SECTIONS = [
  {
    id: 'leads', title: 'Лиды: от заявки до сделки',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>Заявки с сайта, почты, телефонии и API попадают в раздел «Лиды» и автоматически распределяются между менеджерами.</List.Item>
        <List.Item>Откройте лид и нажмите «Взять в работу» — система зафиксирует время реакции (KPI «время обработки лида»).</List.Item>
        <List.Item>Позвоните клиенту кнопкой рядом с телефоном или отправьте письмо — всё сохранится в ленте.</List.Item>
        <List.Item>Если запрос целевой — «Конвертировать в сделку»: в один клик создаются сделка, компания и контакт. Система предупредит, если компания уже есть в базе.</List.Item>
        <List.Item>Если нет — «Отклонить» с указанием причины (нужна для аналитики маркетинга).</List.Item>
      </List>
    ),
  },
  {
    id: 'deals', title: 'Сделки и воронка продаж',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>На канбан-доске перетаскивайте карточки между этапами. Вероятность и прогноз пересчитываются автоматически.</List.Item>
        <List.Item>В карточке сделки на вкладке «Товары и услуги» выберите позиции из каталога — сумма сделки посчитается сама.</List.Item>
        <List.Item>Кнопки «Выиграна» / «Проиграна» закрывают сделку. Для проигрыша причина обязательна.</List.Item>
        <List.Item>Значок ⚠ на карточке — сделка без активности 14+ дней. Каждое утро система напоминает о таких сделках.</List.Item>
      </List>
    ),
  },
  {
    id: 'kp', title: 'Коммерческие предложения',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>Создайте КП из карточки сделки — позиции подтянутся автоматически. Выберите шаблон под отрасль клиента.</List.Item>
        <List.Item>Переменные вида <code>{'{{клиент.название}}'}</code> подставляются при формировании PDF.</List.Item>
        <List.Item>«Отправить клиенту» — письмо с PDF и ссылкой на онлайн-версию. Когда клиент откроет КП, вы получите уведомление.</List.Item>
        <List.Item>Клиент может согласовать или отклонить КП прямо по ссылке — статус обновится автоматически.</List.Item>
      </List>
    ),
  },
  {
    id: 'tasks', title: 'Задачи, календарь и напоминания',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>Задачи создаются из любой карточки или клавишей <Kbd>T</Kbd>. Выберите напоминание: за 15 минут, час или день.</List.Item>
        <List.Item>Напоминания приходят в интерфейс, на email и в Telegram (подключается в профиле).</List.Item>
        <List.Item>В календаре задачи можно переносить мышью. Кнопка «Синхронизация» даёт ссылку для Google Calendar / Outlook.</List.Item>
        <List.Item>При завершении задачи укажите результат — он попадёт в ленту клиента.</List.Item>
      </List>
    ),
  },
  {
    id: 'reports', title: 'Отчёты и аналитика',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>Дашборд показывает ключевые показатели в реальном времени и сравнение с прошлым периодом.</List.Item>
        <List.Item>Стандартные отчёты: воронка, эффективность менеджеров, источники лидов (с CPL и ROI), продукты и маржа, дебиторка.</List.Item>
        <List.Item>«Конструктор отчётов» — любой показатель в разрезе времени, менеджеров, источников, отраслей или регионов.</List.Item>
        <List.Item>Любой отчёт выгружается в PDF, Excel или CSV, а также может приходить на почту еженедельно или ежемесячно.</List.Item>
      </List>
    ),
  },
  {
    id: 'clients', title: 'Клиенты: поиск, сегменты, импорт',
    body: (
      <List size="sm" spacing={6}>
        <List.Item>Глобальный поиск (<Kbd>/</Kbd>) находит компанию по названию, ИНН, телефону (в любом формате) или ФИО контакта.</List.Item>
        <List.Item>Фильтры списка компаний сохраняются при выгрузке: «Выгрузить сегмент» даёт Excel для маркетинговой рассылки.</List.Item>
        <List.Item>Импорт из CSV/Excel: система сама сопоставит колонки, проверит ИНН и не создаст дубли.</List.Item>
      </List>
    ),
  },
];

const VIDEOS = [
  'Первый вход и обзор интерфейса (3 мин)', 'Работа с лидами (5 мин)', 'Канбан и карточка сделки (6 мин)',
  'Коммерческое предложение за 2 минуты (4 мин)', 'Отчёты для руководителя (7 мин)', 'Администрирование системы (8 мин)',
];

export default function HelpPage() {
  const [tour, setTour] = useState(false);
  return (
    <>
      <PageHeader title="Помощь" subtitle="Инструкции, видеоуроки и горячие клавиши"
        actions={<Button leftSection={<IconRoute size={16} />} onClick={() => setTour(true)}>Пройти обучающий тур</Button>} />
      <Grid>
        <Grid.Col span={{ base: 12, md: 8 }}>
          <Card>
            <Group mb="md"><ThemeIcon variant="light"><IconBook size={18} /></ThemeIcon><Title order={4}>Руководство пользователя</Title></Group>
            <Accordion variant="separated" defaultValue="leads">
              {SECTIONS.map((s) => (
                <Accordion.Item key={s.id} value={s.id}>
                  <Accordion.Control>{s.title}</Accordion.Control>
                  <Accordion.Panel>{s.body}</Accordion.Panel>
                </Accordion.Item>
              ))}
            </Accordion>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 4 }}>
          <Stack>
            <Card>
              <Group mb="md"><ThemeIcon variant="light" color="red"><IconPlayerPlay size={18} /></ThemeIcon><Title order={4}>Видеоуроки</Title></Group>
              <Stack gap="xs">
                {VIDEOS.map((v) => <Text key={v} size="sm">▶ {v}</Text>)}
              </Stack>
              <Text size="xs" c="dimmed" mt="sm">Видео записываются на этапе внедрения под ваши процессы и публикуются здесь.</Text>
            </Card>
            <Card>
              <Title order={5} mb="sm">Горячие клавиши</Title>
              <Stack gap={6}>
                {[['/', 'Поиск'], ['C', 'Новая сделка'], ['L', 'Новый лид'], ['T', 'Новая задача'], ['N', 'Новая компания'], ['?', 'Все клавиши']].map(([k, l]) => (
                  <Group key={k} justify="space-between"><Text size="sm">{l}</Text><Kbd>{k}</Kbd></Group>
                ))}
              </Stack>
            </Card>
            <Card>
              <Title order={5} mb="xs">Для разработчиков</Title>
              <Anchor href="/api/docs" target="_blank" size="sm">Документация REST API (Swagger)</Anchor>
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      {tour && <Onboarding forceOpen onClose={() => setTour(false)} />}
    </>
  );
}
