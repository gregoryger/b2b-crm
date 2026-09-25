import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import {
  Badge,
  Card,
  Grid,
  Group,
  Progress,
  SimpleGrid,
  Skeleton,
  Stack,
  Table,
  Text,
  Title,
} from '@mantine/core';
import { BarChart } from '@mantine/charts';
import {
  IconAlertTriangle,
  IconBriefcase,
  IconCash,
  IconChartArrowsVertical,
  IconClockHour4,
  IconPercentage,
  IconTarget,
  IconTrophy,
} from '@tabler/icons-react';
import { useApi } from '@/api/hooks';
import type { Activity, Task } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { UserSelect } from '@/components/selects';
import PeriodPicker, { Period, periodFromPreset } from '@/components/PeriodPicker';
import { CompleteTaskModal, TaskRow } from '@/components/TasksPanel';
import { TaskModal } from '@/components/forms';
import { Empty, PageHeader, QueryFeedback, StatCard } from '@/components/ui';
import { date, money, moneyShort, num, pct, plural, smartDate } from '@/lib/format';

interface Summary {
  revenue: number; won_count: number; lost_count: number; win_rate: number; avg_check: number;
  deals_created: number; open_deals: number; pipeline: number; forecast: number; leads: number;
  lead_conversion: number; avg_lead_response_minutes: number; overdue_tasks: number; payments: number;
}
interface Dashboard {
  summary: Summary;
  previous: Summary;
  revenue_by_month: { month: string; revenue: number; won: number; lost: number }[];
  forecast: { month: string; amount: number; weighted: number; count: number }[];
  funnel: { stage: string; color: string; probability: number; count: number; amount: number }[];
  top_managers: { manager: string; revenue: number; won: number; win_rate: number; pipeline: number }[];
  tasks: Task[];
  activities: Activity[];
}

const diff = (a: number, b: number) => (b ? ((a - b) / Math.abs(b)) * 100 : null);

function greeting() {
  const h = new Date().getHours();
  if (h < 6) return 'Доброй ночи';
  if (h < 12) return 'Доброе утро';
  if (h < 18) return 'Добрый день';
  return 'Добрый вечер';
}

function responseLabel(minutes: number) {
  if (!minutes) return '—';
  if (minutes < 60) return `${num(minutes)} мин`;
  return `${num(minutes / 60, 1)} ч`;
}

export default function DashboardPage() {
  const { user, can } = useAuth();
  const navigate = useNavigate();
  const [period, setPeriod] = useState<Period>(periodFromPreset('month'));
  const [ownerId, setOwnerId] = useState<number | null>(null);
  const [task, setTask] = useState<Task | null>(null);
  const [completing, setCompleting] = useState<Task | null>(null);
  const query = useApi<Dashboard>(['dashboard'], '/analytics/dashboard', {
    date_from: period.from, date_to: period.to, owner_id: ownerId ?? undefined,
  });
  const { data, isLoading } = query;
  const s = data?.summary;
  const p = data?.previous;
  const team = can('analytics.team');
  const maxFunnel = Math.max(1, ...(data?.funnel.map((f) => f.amount) ?? [1]));

  return (
    <div data-tour="dashboard">
      <PageHeader
        title={`${greeting()}, ${user?.full_name.split(' ')[1] ?? ''}!`}
        subtitle={team ? 'Показатели отдела продаж' : 'Ваши показатели'}
        actions={
          <>
            {team && (
              <UserSelect w={220} placeholder="Весь отдел" role="manager,head" value={ownerId} onChange={setOwnerId}
                aria-label="Менеджер" />
            )}
            <PeriodPicker value={period} onChange={setPeriod} />
          </>
        }
      />
      {query.isError && <QueryFeedback query={query} hasData={!!data} />}
      {isLoading ? (
        <SimpleGrid cols={{ base: 1, sm: 2, lg: 4 }}>
          {Array.from({ length: 8 }).map((_, i) => <Skeleton key={i} h={110} radius="md" />)}
        </SimpleGrid>
      ) : s && p && data ? (
        <Stack>
          <SimpleGrid cols={{ base: 1, xs: 2, lg: 4 }}>
            <StatCard label="Выручка" value={moneyShort(s.revenue)} diff={diff(s.revenue, p.revenue)}
              hint="к пред. периоду" icon={<IconCash size={20} />} color="teal" />
            <StatCard label="Выиграно сделок" value={num(s.won_count)} diff={diff(s.won_count, p.won_count)}
              hint={`win rate ${pct(s.win_rate)}`} icon={<IconTrophy size={20} />} color="yellow" />
            <StatCard label="Средний чек" value={moneyShort(s.avg_check)} diff={diff(s.avg_check, p.avg_check)}
              hint="к пред. периоду" icon={<IconChartArrowsVertical size={20} />} />
            <StatCard label="Конверсия лид → сделка" value={pct(s.lead_conversion)}
              hint={`${num(s.leads)} ${plural(s.leads, ['новый лид', 'новых лида', 'новых лидов'])}`} icon={<IconPercentage size={20} />} color="violet" />
            <StatCard label="В работе" value={moneyShort(s.pipeline)} hint={`${num(s.open_deals)} ${plural(s.open_deals, ['сделка', 'сделки', 'сделок'])}`}
              onClick={can('deals.view') ? () => navigate(`/deals?view=list&status=open&owner=${ownerId ?? ''}`) : undefined}
              icon={<IconBriefcase size={20} />} color="indigo" />
            <StatCard label="Прогноз (взвешенный)" value={moneyShort(s.forecast)} hint="сумма × вероятность этапа"
              icon={<IconTarget size={20} />} color="cyan" />
            <StatCard label="Реакция на лид" value={responseLabel(s.avg_lead_response_minutes)}
              hint="среднее время первого ответа" icon={<IconClockHour4 size={20} />} color="orange"
              diff={s.avg_lead_response_minutes && p.avg_lead_response_minutes
                ? -(diff(s.avg_lead_response_minutes, p.avg_lead_response_minutes) ?? 0) : null} />
            <StatCard label="Просроченные задачи" value={num(s.overdue_tasks)} hint={s.overdue_tasks ? plural(s.overdue_tasks, ['требует внимания', 'требуют внимания', 'требуют внимания']) : 'всё в срок'}
              onClick={() => navigate(`/tasks?tab=overdue&scope=${can('tasks.view_all') ? 'all' : 'mine'}&assignee=${ownerId ?? ''}`)}
              icon={<IconAlertTriangle size={20} />} color={s.overdue_tasks ? 'red' : 'gray'} />
          </SimpleGrid>

          <Grid>
            <Grid.Col span={{ base: 12, lg: 8 }}>
              <Card h="100%">
                <Group justify="space-between" mb="md">
                  <Title order={4}>Выручка по месяцам</Title>
                  <Text size="xs" c="dimmed">
                    {data!.revenue_by_month.length} мес. по {date(period.to)} · выигранные сделки, ₽
                  </Text>
                </Group>
                <BarChart h={280} data={data!.revenue_by_month} dataKey="month"
                  series={[{ name: 'revenue', label: 'Выручка', color: 'teal.6' }]}
                  valueFormatter={(v) => moneyShort(v)} tickLine="none" gridAxis="y" barProps={{ radius: 4 }}
                  yAxisProps={{ width: 90 }} />
              </Card>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 4 }}>
              <Card h="100%">
                <Group justify="space-between" mb="md">
                  <Title order={4}>Воронка продаж</Title>
                  <Text size="sm" className="link" onClick={() => navigate('/deals')}>
                    Канбан
                  </Text>
                </Group>
                <Stack gap={10}>
                  {data!.funnel.map((f) => (
                    <div key={f.stage}>
                      <Group justify="space-between" gap={4}>
                        <Text size="sm">{f.stage}</Text>
                        <Text size="xs" c="dimmed">
                          {num(f.count)} · {moneyShort(f.amount)}
                        </Text>
                      </Group>
                      <Progress value={(f.amount / maxFunnel) * 100} color={f.color === 'gray' ? 'blue' : f.color}
                        size="lg" radius="sm" mt={4} />
                    </div>
                  ))}
                  <Text size="xs" c="dimmed">
                    Сделки в работе сейчас: количество и сумма на каждом этапе
                  </Text>
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>

          <Grid>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Card h="100%">
                <Group justify="space-between" mb="xs">
                  <Title order={4}>Мои задачи</Title>
                  <Text size="sm" className="link" onClick={() => navigate('/tasks')}>
                    Все задачи
                  </Text>
                </Group>
                {!data!.tasks.length ? (
                  <Empty text="На сегодня задач нет 🎉" />
                ) : (
                  <Stack gap={0}>
                    {data!.tasks.map((t) => (
                      <TaskRow key={t.id} task={t} onOpen={setTask} onComplete={setCompleting} />
                    ))}
                  </Stack>
                )}
              </Card>
            </Grid.Col>
            <Grid.Col span={{ base: 12, lg: 6 }}>
              <Card h="100%">
                <Group justify="space-between" mb="md">
                  <Title order={4}>Прогноз закрытия</Title>
                  <Text size="xs" c="dimmed">
                    ближайшие 6 месяцев · по плановым датам, ₽
                  </Text>
                </Group>
                <BarChart h={250} data={data!.forecast} dataKey="month"
                  series={[{ name: 'amount', label: 'Сумма сделок', color: 'blue.2' },
                    { name: 'weighted', label: 'С учётом вероятности', color: 'blue.7' }]}
                  valueFormatter={(v) => moneyShort(v)} withLegend legendProps={{ verticalAlign: 'bottom' }}
                  tickLine="none" gridAxis="y" yAxisProps={{ width: 90 }} />
              </Card>
            </Grid.Col>
          </Grid>

          <Grid>
            {team && (
              <Grid.Col span={{ base: 12, lg: 6 }}>
                <Card h="100%">
                  <Group justify="space-between" mb="xs">
                    <Title order={4}>Топ менеджеров</Title>
                    <Text size="sm" className="link" onClick={() => navigate('/reports?report=managers')}>
                      Подробнее
                    </Text>
                  </Group>
                  <Table>
                    <Table.Thead>
                      <Table.Tr>
                        <Table.Th>Менеджер</Table.Th>
                        <Table.Th ta="right">Выручка</Table.Th>
                        <Table.Th ta="right">Сделок</Table.Th>
                        <Table.Th ta="right">Win rate</Table.Th>
                      </Table.Tr>
                    </Table.Thead>
                    <Table.Tbody>
                      {data!.top_managers.map((m, i) => (
                        <Table.Tr key={m.manager}>
                          <Table.Td>
                            <Group gap={6} wrap="nowrap">
                              {i === 0 && m.revenue > 0 && <Badge size="xs" color="yellow">1</Badge>}
                              <Text size="sm">{m.manager}</Text>
                            </Group>
                          </Table.Td>
                          <Table.Td ta="right">{money(m.revenue)}</Table.Td>
                          <Table.Td ta="right">{m.won}</Table.Td>
                          <Table.Td ta="right">{pct(m.win_rate)}</Table.Td>
                        </Table.Tr>
                      ))}
                    </Table.Tbody>
                  </Table>
                </Card>
              </Grid.Col>
            )}
            <Grid.Col span={{ base: 12, lg: team ? 6 : 12 }}>
              <Card h="100%">
                <Title order={4} mb="xs">
                  Последние события
                </Title>
                <Stack gap={8}>
                  {data!.activities.map((a) => (
                    <Group key={a.id} justify="space-between" wrap="nowrap" gap="sm"
                      style={{ cursor: a.deal_id || a.company_id ? 'pointer' : undefined }}
                      onClick={() => {
                        if (a.deal_id && can('deals.view')) navigate(`/deals/${a.deal_id}`);
                        else if (a.company_id) navigate(`/companies/${a.company_id}`);
                        else if (a.lead_id) navigate(`/leads/${a.lead_id}`);
                      }}>
                      <div style={{ minWidth: 0 }}>
                        <Text size="sm" truncate>
                          {a.title}
                        </Text>
                        <Text size="xs" c="dimmed">
                          {a.user?.full_name ?? 'Система'}
                        </Text>
                      </div>
                      <Text size="xs" c="dimmed" style={{ whiteSpace: 'nowrap' }}>
                        {smartDate(a.occurred_at)}
                      </Text>
                    </Group>
                  ))}
                </Stack>
              </Card>
            </Grid.Col>
          </Grid>
        </Stack>
      ) : null}
      <TaskModal opened={!!task} onClose={() => setTask(null)} task={task} />
      <CompleteTaskModal task={completing} onClose={() => setCompleting(null)} />
    </div>
  );
}
