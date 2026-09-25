import { useState } from 'react';
import { useSearchParams } from 'react-router-dom';
import {
  ActionIcon,
  Badge,
  Button,
  Card,
  Grid,
  Group,
  Menu,
  Modal,
  NavLink,
  Paper,
  SegmentedControl,
  Select,
  SimpleGrid,
  Stack,
  Switch,
  Table,
  Text,
  TextInput,
  Title,
} from '@mantine/core';
import { BarChart, DonutChart, LineChart } from '@mantine/charts';
import { IconCalendarRepeat, IconDownload, IconSend, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, download, notifyError, notifyOk } from '@/api/client';
import { useApi, useDict, useUsers } from '@/api/hooks';
import type { Report, ReportColumn } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import PeriodPicker, { Period, periodFromPreset } from '@/components/PeriodPicker';
import { Empty, PageHeader, QueryFeedback } from '@/components/ui';
import { date, dateTime, money, moneyShort, num, pct } from '@/lib/format';

const REPORTS = [
  { key: 'summary', title: 'Сводный отчёт' },
  { key: 'funnel', title: 'Воронка продаж' },
  { key: 'managers', title: 'Эффективность менеджеров' },
  { key: 'sources', title: 'Источники лидов' },
  { key: 'products', title: 'Продуктовая аналитика' },
  { key: 'receivables', title: 'Дебиторская задолженность', perm: 'finance.view' },
  { key: 'custom', title: 'Конструктор отчётов' },
];
const METRICS = [
  { value: 'revenue', label: 'Выручка' }, { value: 'deals_won', label: 'Выигранные сделки' },
  { value: 'deals_created', label: 'Новые сделки' }, { value: 'leads', label: 'Лиды' },
  { value: 'activities', label: 'Активности' }, { value: 'payments', label: 'Поступления' },
];
const GROUPS = [
  { value: 'day', label: 'По дням' }, { value: 'week', label: 'По неделям' }, { value: 'month', label: 'По месяцам' },
  { value: 'manager', label: 'По менеджерам' }, { value: 'source', label: 'По источникам' },
  { value: 'industry', label: 'По отраслям' }, { value: 'region', label: 'По регионам' }, { value: 'stage', label: 'По этапам' },
];
const PALETTE = ['blue.6', 'teal.6', 'violet.6', 'orange.6', 'cyan.6', 'grape.6', 'lime.7', 'red.6', 'indigo.6', 'yellow.7'];

function cell(v: any, t: ReportColumn['type']) {
  if (v === null || v === undefined || v === '') return '—';
  if (t === 'money') return money(v);
  if (t === 'pct') return pct(v);
  if (t === 'int' || t === 'float') return num(v, 2);
  if (t === 'date') return date(v);
  return String(v);
}

function ReportChart({ name, report, chartType }: { name: string; report: Report; chartType: string }) {
  const rows = report.rows;
  if (!rows.length) return null;
  const fmt = (v: number) => moneyShort(v);
  switch (name) {
    case 'funnel':
      return <BarChart h={300} data={rows} dataKey="stage" orientation="vertical" yAxisProps={{ width: 170 }}
        series={[{ name: 'reached', label: 'Дошло сделок', color: 'blue.6' }]} gridAxis="x" />;
    case 'managers':
      return <BarChart h={300} data={rows} dataKey="manager" valueFormatter={fmt} withLegend
        series={[{ name: 'revenue', label: 'Выручка', color: 'teal.6' }, { name: 'pipeline', label: 'В работе', color: 'blue.3' }]} />;
    case 'sources':
      return (
        <SimpleGrid cols={{ base: 1, md: 2 }}>
          <BarChart h={280} data={rows} dataKey="source" withLegend
            series={[{ name: 'leads', label: 'Лиды', color: 'blue.5' }, { name: 'deals', label: 'Сделки', color: 'teal.6' }]} />
          <DonutChart h={280} withLabelsLine withLabels chartLabel="Лиды" mx="auto"
            data={rows.filter((r) => r.leads).map((r, i) => ({ name: r.source, value: r.leads, color: PALETTE[i % PALETTE.length] }))} />
        </SimpleGrid>
      );
    case 'products':
      return <BarChart h={300} data={rows.slice(0, 10)} dataKey="product" valueFormatter={fmt} withLegend orientation="vertical"
        yAxisProps={{ width: 220 }} series={[{ name: 'revenue', label: 'Выручка', color: 'blue.6' }, { name: 'margin', label: 'Маржа', color: 'teal.6' }]} />;
    case 'custom': {
      const money_ = report.columns[1]?.type === 'money';
      const vf = (v: number) => (money_ ? moneyShort(v) : num(v));
      if (chartType === 'pie')
        return <DonutChart h={300} withLabels withLabelsLine mx="auto" valueFormatter={vf}
          data={rows.map((r, i) => ({ name: r.group, value: r.value, color: PALETTE[i % PALETTE.length] }))} />;
      if (chartType === 'line')
        return <LineChart h={300} data={rows} dataKey="group" valueFormatter={vf} curveType="monotone"
          series={[{ name: 'value', label: report.columns[1].label, color: 'blue.6' }]} />;
      return <BarChart h={300} data={rows} dataKey="group" valueFormatter={vf}
        series={[{ name: 'value', label: report.columns[1].label, color: 'blue.6' }]} />;
    }
    default:
      return null;
  }
}

function SchedulesModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const { data } = useApi<{ id: number; report: string; frequency: string; format: string; email: string; is_active: boolean;
    last_sent_at: string | null }[]>(['schedules'], opened ? '/analytics/schedules' : null);
  const [report, setReport] = useState<string | null>('summary');
  const [freq, setFreq] = useState('weekly');
  const [format, setFormat] = useState('pdf');
  const [email, setEmail] = useState(user?.email ?? '');
  const refresh = () => qc.invalidateQueries({ queryKey: ['schedules'] });
  const add = async () => {
    try {
      await api.post('/analytics/schedules', { report, frequency: freq, format, email });
      notifyOk('Рассылка настроена');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const title = (k: string) => REPORTS.find((r) => r.key === k)?.title ?? k;
  return (
    <Modal opened={opened} onClose={onClose} title="Автоматическая рассылка отчётов" size="lg">
      <Stack>
        <Text size="sm" c="dimmed">Еженедельные отчёты приходят по понедельникам (за прошлую неделю), ежемесячные — 1-го числа.</Text>
        {data?.map((s) => (
          <Paper withBorder p="sm" key={s.id}>
            <Group justify="space-between">
              <div>
                <Text size="sm" fw={500}>{title(s.report)} · {s.frequency === 'weekly' ? 'еженедельно' : 'ежемесячно'} · {s.format.toUpperCase()}</Text>
                <Text size="xs" c="dimmed">{s.email}{s.last_sent_at && ` · последняя отправка ${dateTime(s.last_sent_at)}`}</Text>
              </div>
              <Group gap={4}>
                <Switch checked={s.is_active} aria-label="Активна" onChange={async (e) => {
                  await api.patch(`/analytics/schedules/${s.id}`, { ...s, is_active: e.currentTarget.checked }).catch(notifyError);
                  refresh();
                }} />
                <ActionIcon variant="subtle" aria-label="Отправить сейчас" onClick={async () => {
                  try {
                    const { data: r } = await api.post(`/analytics/schedules/${s.id}/send-now`);
                    notifyOk(r.detail);
                  } catch (e) {
                    notifyError(e);
                  }
                }}><IconSend size={16} /></ActionIcon>
                <ActionIcon variant="subtle" color="red" aria-label="Удалить" onClick={async () => {
                  await api.delete(`/analytics/schedules/${s.id}`).catch(notifyError);
                  refresh();
                }}><IconTrash size={16} /></ActionIcon>
              </Group>
            </Group>
          </Paper>
        ))}
        <Paper withBorder p="md" bg="gray.0">
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            <Select label="Отчёт" data={REPORTS.filter((r) => r.key !== 'custom').map((r) => ({ value: r.key, label: r.title }))}
              value={report} onChange={setReport} allowDeselect={false} />
            <TextInput label="Email" value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
            <SegmentedControl value={freq} onChange={setFreq} data={[{ value: 'weekly', label: 'Еженедельно' }, { value: 'monthly', label: 'Ежемесячно' }]} />
            <SegmentedControl value={format} onChange={setFormat} data={['pdf', 'xlsx', 'csv'].map((v) => ({ value: v, label: v.toUpperCase() }))} />
          </SimpleGrid>
          <Button mt="md" onClick={add} disabled={!email}>Добавить рассылку</Button>
        </Paper>
      </Stack>
    </Modal>
  );
}

export default function ReportsPage() {
  const { can } = useAuth();
  const [params] = useSearchParams();
  const [name, setName] = useState(params.get('report') || 'summary');
  const [period, setPeriod] = useState<Period>(periodFromPreset('quarter'));
  const [owner, setOwner] = useState<string | null>(null);
  const [source, setSource] = useState<string | null>(null);
  const [industry, setIndustry] = useState<string | null>(null);
  const [region, setRegion] = useState<string | null>(null);
  const [metric, setMetric] = useState<string | null>('revenue');
  const [group, setGroup] = useState<string | null>('month');
  const [chartType, setChartType] = useState('bar');
  const [schedules, setSchedules] = useState(false);
  const users = useUsers('manager,head');
  const sources = useDict('lead_source');
  const industries = useDict('industry');
  const regions = useDict('region');
  const query = {
    date_from: period.from, date_to: period.to, owner_id: owner ?? undefined, source_id: source ?? undefined,
    industry_id: industry ?? undefined, region_id: region ?? undefined,
    ...(name === 'custom' ? { metric, group_by: group } : {}),
  };
  const reportQuery = useApi<Report>(['report', name], `/analytics/reports/${name}`, query);
  const { data } = reportQuery;
  const reports = REPORTS.filter((r) => !r.perm || can(r.perm));

  return (
    <>
      <PageHeader title="Отчёты" subtitle="Аналитика продаж, маркетинга и финансов"
        actions={
          <>
            <Button variant="default" leftSection={<IconCalendarRepeat size={16} />} onClick={() => setSchedules(true)}>Рассылка по расписанию</Button>
            <Menu>
              <Menu.Target><Button leftSection={<IconDownload size={16} />}>Экспорт</Button></Menu.Target>
              <Menu.Dropdown>
                {['pdf', 'xlsx', 'csv'].map((f) => (
                  <Menu.Item key={f} onClick={() => download(`/analytics/reports/${name}/export`, { ...query, format: f }, `report.${f}`)}>
                    {f === 'pdf' ? 'PDF' : f === 'xlsx' ? 'Excel (.xlsx)' : 'CSV'}
                  </Menu.Item>
                ))}
              </Menu.Dropdown>
            </Menu>
          </>
        } />
      <Grid>
        <Grid.Col span={{ base: 12, md: 3 }}>
          <Card p="xs">
            {reports.map((r) => (
              <NavLink key={r.key} label={r.title} active={name === r.key} onClick={() => setName(r.key)} style={{ borderRadius: 8 }}
                rightSection={r.key === 'custom' ? <Badge size="xs">new</Badge> : undefined} />
            ))}
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, md: 9 }}>
          <Stack>
            <Paper withBorder p="md">
              <Group gap="sm">
                {name !== 'receivables' && <PeriodPicker value={period} onChange={setPeriod} />}
                {can('analytics.team') && (
                  <Select placeholder="Все менеджеры" w={200} clearable searchable data={users.options} value={owner} onChange={setOwner} aria-label="Менеджер" />
                )}
                {['summary', 'funnel', 'products', 'custom', 'managers'].includes(name) && (
                  <>
                    <Select placeholder="Источник" w={170} clearable data={sources.options} value={source} onChange={setSource} aria-label="Источник" />
                    <Select placeholder="Отрасль" w={170} clearable data={industries.options} value={industry} onChange={setIndustry} aria-label="Отрасль" />
                    <Select placeholder="Регион" w={170} clearable searchable data={regions.options} value={region} onChange={setRegion} aria-label="Регион" />
                  </>
                )}
              </Group>
              {name === 'custom' && (
                <Group gap="sm" mt="sm">
                  <Select label="Показатель" data={METRICS} value={metric} onChange={setMetric} allowDeselect={false} w={200} />
                  <Select label="Группировка" data={GROUPS} value={group} onChange={setGroup} allowDeselect={false} w={200} />
                  <div>
                    <Text size="sm" fw={500} mb={4}>Тип графика</Text>
                    <SegmentedControl value={chartType} onChange={setChartType}
                      data={[{ value: 'bar', label: 'Столбцы' }, { value: 'line', label: 'Линия' }, { value: 'pie', label: 'Круговая' }]} />
                  </div>
                </Group>
              )}
            </Paper>
            <QueryFeedback query={reportQuery} hasData={!!data} />
            {data ? (
              <Card>
                <Title order={4}>{data.title}</Title>
                <Text size="sm" c="dimmed" mb="md">{data.subtitle}</Text>
                {name !== 'summary' && name !== 'receivables' && <ReportChart name={name} report={data} chartType={chartType} />}
                {name === 'summary' ? (
                  <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} mt="md">
                    {data.rows.map((r) => (
                      <Paper withBorder p="md" key={r.metric}>
                        <Text size="xs" c="dimmed">{r.metric}</Text>
                        <Text fw={700} size="xl">{cell(r.value, r.type)}</Text>
                      </Paper>
                    ))}
                  </SimpleGrid>
                ) : !data.rows.length ? <Empty text="Нет данных за выбранный период" /> : (
                  <Table.ScrollContainer minWidth={700} mt="lg">
                    <Table striped>
                      <Table.Thead>
                        <Table.Tr>{data.columns.map((c) => <Table.Th key={c.key} ta={c.type === 'text' ? 'left' : 'right'}>{c.label}</Table.Th>)}</Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {data.rows.map((r, i) => (
                          <Table.Tr key={i}>
                            {data.columns.map((c) => <Table.Td key={c.key} ta={c.type === 'text' ? 'left' : 'right'}>{cell(r[c.key], c.type)}</Table.Td>)}
                          </Table.Tr>
                        ))}
                        {data.totals && (
                          <Table.Tr fw={700}>
                            {data.columns.map((c) => <Table.Td key={c.key} ta={c.type === 'text' ? 'left' : 'right'}>
                              {data.totals![c.key] !== undefined ? cell(data.totals![c.key], c.type) : ''}
                            </Table.Td>)}
                          </Table.Tr>
                        )}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                )}
              </Card>
            ) : null}
          </Stack>
        </Grid.Col>
      </Grid>
      <SchedulesModal opened={schedules} onClose={() => setSchedules(false)} />
    </>
  );
}
