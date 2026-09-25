import { useListState } from '@/lib/useListState';
import { useEffect, useState } from 'react';
import { useNavigate, useSearchParams } from 'react-router-dom';
import {
  Avatar,
  Badge,
  Button,
  Card,
  Group,
  MultiSelect,
  Paper,
  SegmentedControl,
  Select,
  Stack,
  Table,
  Text,
  TextInput,
  Tooltip,
} from '@mantine/core';
import { DragDropContext, Draggable, Droppable, DropResult } from '@hello-pangea/dnd';
import { useDebouncedValue } from '@mantine/hooks';
import { IconAlertTriangle, IconCalendarDue, IconLayoutKanban, IconList, IconPlus, IconSearch } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError } from '@/api/client';
import { useApi, useStages, useUsers } from '@/api/hooks';
import type { BoardColumn, Deal, Page } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { useQuickCreate } from '@/components/QuickCreate';
import SortTh from '@/components/SortTh';
import { Empty, PageHeader, Pager, QueryFeedback, StatusBadge } from '@/components/ui';
import { date, dayjs, initials, money, moneyShort, num, plural } from '@/lib/format';
import { DEAL_STATUS } from '@/lib/labels';
import LostModal from './LostModal';

function DealCardMini({ d }: { d: Deal }) {
  const overdue = d.status === 'open' && d.close_date && dayjs(d.close_date).isBefore(dayjs(), 'day');
  const stale = d.is_stale;
  return (
    <Card padding="sm" className="kanban-card" radius="md">
      <Text size="sm" fw={600} lineClamp={2}>{d.title}</Text>
      {d.company && <Text size="xs" c="dimmed" truncate>{d.company.name}</Text>}
      <Group justify="space-between" mt={8} wrap="nowrap">
        <Text size="sm" fw={700}>{money(d.amount, d.currency)}</Text>
        <Badge size="xs" variant="light" color="gray">{d.probability}%</Badge>
      </Group>
      <Group justify="space-between" mt={6} wrap="nowrap">
        <Group gap={4} wrap="nowrap">
          {d.close_date && (
            <Text size="xs" c={overdue ? 'red' : 'dimmed'} style={{ display: 'flex', alignItems: 'center', gap: 2 }}>
              <IconCalendarDue size={12} /> {date(d.close_date)}
            </Text>
          )}
          {stale && (
            <Tooltip label="Нет активности 14+ дней">
              <IconAlertTriangle size={14} color="var(--mantine-color-orange-6)" />
            </Tooltip>
          )}
        </Group>
        {d.owner && (
          <Tooltip label={d.owner.full_name}>
            <Avatar size={22} radius="xl" color="blue">{initials(d.owner.full_name)}</Avatar>
          </Tooltip>
        )}
      </Group>
    </Card>
  );
}

function Board({ columns, onMove, onLoadMore, loadingStage }: {
  columns: BoardColumn[]; onMove: (dealId: number, stageId: number) => void;
  onLoadMore: (stageId: number) => void; loadingStage: number | null;
}) {
  const navigate = useNavigate();
  const onDragEnd = (r: DropResult) => {
    if (!r.destination || r.destination.droppableId === r.source.droppableId) return;
    onMove(Number(r.draggableId), Number(r.destination.droppableId));
  };
  return (
    <DragDropContext onDragEnd={onDragEnd}>
      <div className="kanban">
        {columns.map((col) => (
          <div className="kanban-col" key={col.stage.id}>
            <div style={{ padding: '10px 12px 6px', borderTop: `3px solid var(--mantine-color-${col.stage.color}-5)`, borderRadius: '10px 10px 0 0' }}>
              <Group justify="space-between" wrap="nowrap">
                <Text fw={600} size="sm" truncate>{col.stage.name}</Text>
                <Badge size="sm" variant="white" color="gray">{col.count}</Badge>
              </Group>
              <Text size="xs" c="dimmed">
                {moneyShort(col.amount)}
                {col.stage.kind === 'open' && ` · прогноз ${moneyShort(col.weighted)}`}
              </Text>
            </div>
            <Droppable droppableId={String(col.stage.id)}>
              {(provided, snapshot) => (
                <div ref={provided.innerRef} {...provided.droppableProps}
                  className={`kanban-col-body${snapshot.isDraggingOver ? ' drag-over' : ''}`}>
                  {col.deals.map((d, idx) => (
                    <Draggable draggableId={String(d.id)} index={idx} key={d.id}>
                      {(p) => (
                        <div ref={p.innerRef} {...p.draggableProps} {...p.dragHandleProps}
                          onClick={() => navigate(`/deals/${d.id}`)}>
                          <DealCardMini d={d} />
                        </div>
                      )}
                    </Draggable>
                  ))}
                  {provided.placeholder}
                  {col.deals.length < col.count && (
                    <Button fullWidth variant="light" size="xs" mt="xs" loading={loadingStage === col.stage.id}
                      disabled={loadingStage !== null && loadingStage !== col.stage.id} onClick={() => onLoadMore(col.stage.id)}>
                      Показать ещё · {col.deals.length} из {col.count}
                    </Button>
                  )}
                  {!col.deals.length && <Text size="xs" c="dimmed" ta="center" py="md">Перетащите сделку сюда</Text>}
                </div>
              )}
            </Droppable>
          </div>
        ))}
      </div>
    </DragDropContext>
  );
}

export default function DealsPage() {
  const navigate = useNavigate();
  const qc = useQueryClient();
  const { can } = useAuth();
  const { open } = useQuickCreate();
  const [params] = useSearchParams();
  const stale = params.get('stale') === '1';
  const [view, setView] = useListState('view', stale ? 'list' : 'board');
  const [q, setQ] = useListState('q', '');
  const [debounced] = useDebouncedValue(q, 300);
  const [owner, setOwner] = useListState<string | null>('owner', null);
  const [statuses, setStatuses] = useListState<string[]>('statuses', ['open']);
  const [stageIds, setStageIds] = useListState<string[]>('stageIds', []);
  const [sort, setSort] = useListState('sort', '-created_at');
  const [page, setPage] = useListState('page', 1);
  const [pageSize, setPageSize] = useListState('pageSize', 25);
  const [lost, setLost] = useState<{ dealId: number; stageId: number } | null>(null);
  const [loadingStage, setLoadingStage] = useState<number | null>(null);
  useEffect(() => {
    if (params.get('view') === 'list' || stale) setView('list');
    if (params.has('status')) { setStatuses(params.get('status') === 'open' ? ['open'] : []); setStageIds([]); setQ(''); setPage(1); }
    if (params.has('owner')) setOwner(params.get('owner') || null);
  }, [params, stale]);
  const users = useUsers('manager,head');
  const { data: stages } = useStages();
  const common = { q: debounced || undefined, owner_id: owner ?? undefined };
  const board = useApi<BoardColumn[]>(['board'], view === 'board' ? '/deals/board' : null, common);
  const list = useApi<Page<Deal>>(['deals'], view === 'list' ? '/deals' : null, {
    ...common, status: statuses, stage_id: stageIds, sort, page, page_size: pageSize, stale: stale || undefined,
  });

  const loadMore = async (stageId: number) => {
    if (loadingStage !== null) return;
    const column = board.data?.find((c) => c.stage.id === stageId);
    if (!column) return;
    setLoadingStage(stageId);
    try {
      const { data } = await api.get<BoardColumn[]>('/deals/board', { params: {
        ...common, stage_id: stageId, offset: column.deals.length,
      } });
      const next = data[0];
      if (next) qc.setQueryData<BoardColumn[]>(['board', common], (cols) => cols?.map((c) => c.stage.id === stageId
        ? { ...next, deals: [...c.deals, ...next.deals.filter((d) => !c.deals.some((old) => old.id === d.id))] } : c));
    } catch (error) { notifyError(error); }
    finally { setLoadingStage(null); }
  };

  const move = async (dealId: number, stageId: number, lostReasonId?: number, comment?: string) => {
    const stage = stages?.find((s) => s.id === stageId);
    if (stage?.kind === 'lost' && !lostReasonId) return setLost({ dealId, stageId });
    // оптимистичное обновление доски
    qc.setQueryData<BoardColumn[]>(['board', common], (cols) => {
      if (!cols) return cols;
      const deal = cols.flatMap((c) => c.deals).find((d) => d.id === dealId);
      if (!deal) return cols;
      return cols.map((c) => ({
        ...c,
        deals: c.stage.id === stageId ? [{ ...deal, stage: c.stage, probability: c.stage.probability }, ...c.deals]
          : c.deals.filter((d) => d.id !== dealId),
      }));
    });
    try {
      await api.post(`/deals/${dealId}/move`, { stage_id: stageId, lost_reason_id: lostReasonId, lost_comment: comment });
    } catch (e) {
      notifyError(e);
    } finally {
      ['board', 'deals', 'dashboard'].forEach((k) => qc.invalidateQueries({ queryKey: [k] }));
    }
  };

  const totals = board.data?.filter((c) => c.stage.kind === 'open');
  return (
    <>
      <PageHeader title={stale ? 'Сделки без активности 14+ дней' : 'Сделки'}
        subtitle={totals && `В работе ${num(totals.reduce((s, c) => s + c.count, 0))} ${plural(totals.reduce((s, c) => s + c.count, 0), ['сделка', 'сделки', 'сделок'])} на ${moneyShort(totals.reduce((s, c) => s + c.amount, 0))} · прогноз ${moneyShort(totals.reduce((s, c) => s + c.weighted, 0))}`}
        actions={
          <>
            <SegmentedControl value={view} onChange={setView} data={[
              { value: 'board', label: <Group gap={4} wrap="nowrap"><IconLayoutKanban size={16} />Канбан</Group> },
              { value: 'list', label: <Group gap={4} wrap="nowrap"><IconList size={16} />Список</Group> },
            ]} />
            {can('deals.edit') && <Button leftSection={<IconPlus size={16} />} onClick={() => open('deal')}>Сделка</Button>}
          </>
        } />
      <Paper withBorder p="md" mb="md">
        <Group>
          <TextInput leftSection={<IconSearch size={16} />} placeholder="Название сделки или компании" w={300}
            value={q} onChange={(e) => { setQ(e.currentTarget.value); setPage(1); }} aria-label="Поиск" />
          {can('deals.view_all') && (
            <Select placeholder="Все менеджеры" data={users.options} value={owner} onChange={(v) => { setOwner(v); setPage(1); }}
              w={230} clearable searchable aria-label="Менеджер" />
          )}
          {view === 'list' && (
            <>
              <MultiSelect placeholder="Статус" w={220} value={statuses} onChange={(v) => { setStatuses(v); setPage(1); }}
                data={Object.entries(DEAL_STATUS).map(([value, s]) => ({ value, label: s.label }))} clearable aria-label="Статус" />
              <MultiSelect placeholder="Этап" w={260} value={stageIds} onChange={(v) => { setStageIds(v); setPage(1); }}
                data={(stages ?? []).map((s) => ({ value: String(s.id), label: s.name }))} clearable aria-label="Этап" />
            </>
          )}
        </Group>
      </Paper>

      <QueryFeedback query={view === 'board' ? board : list} hasData={!!(view === 'board' ? board.data : list.data)} />
      {view === 'board' ? (
        board.data ? <Board columns={board.data} onMove={(d, s) => move(d, s)} onLoadMore={loadMore} loadingStage={loadingStage} /> : <Stack h={300} />
      ) : (
        <>
          <Paper withBorder>
            <Table.ScrollContainer minWidth={900}>
              <Table>
                <Table.Thead>
                  <Table.Tr>
                    <SortTh field="title" sort={sort} onSort={setSort}>Сделка</SortTh>
                    <Table.Th>Этап</Table.Th>
                    <SortTh field="amount" sort={sort} onSort={setSort} ta="right">Сумма</SortTh>
                    <SortTh field="probability" sort={sort} onSort={setSort} ta="right">Вероятность</SortTh>
                    <SortTh field="close_date" sort={sort} onSort={setSort}>Закрытие</SortTh>
                    <Table.Th>Ответственный</Table.Th>
                    <SortTh field="updated_at" sort={sort} onSort={setSort}>Обновлена</SortTh>
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {list.data?.items.map((d) => (
                    <Table.Tr key={d.id} className="clickable-row" onClick={() => navigate(`/deals/${d.id}`)}>
                      <Table.Td>
                        <Text size="sm" fw={500}>{d.title}</Text>
                        <Text size="xs" c="dimmed">{d.company?.name}</Text>
                      </Table.Td>
                      <Table.Td>
                        {d.status === 'open' ? <Badge color={d.stage.color}>{d.stage.name}</Badge> : <StatusBadge map={DEAL_STATUS} value={d.status} />}
                      </Table.Td>
                      <Table.Td ta="right">{money(d.amount, d.currency)}</Table.Td>
                      <Table.Td ta="right">{d.probability}%</Table.Td>
                      <Table.Td>
                        <Text size="sm" c={d.status === 'open' && d.close_date && dayjs(d.close_date).isBefore(dayjs(), 'day') ? 'red' : undefined}>
                          {date(d.closed_at ?? d.close_date)}
                        </Text>
                      </Table.Td>
                      <Table.Td><Text size="sm">{d.owner?.full_name}</Text></Table.Td>
                      <Table.Td><Text size="sm">{date(d.updated_at)}</Text></Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            {!list.isLoading && !list.isError && !list.data?.items.length && <Empty text="Сделок не найдено" />}
          </Paper>
          {list.data && <Pager page={page} pages={list.data.pages} total={list.data.total} pageSize={pageSize} onPage={setPage}
            onPageSize={(s) => { setPageSize(s); setPage(1); }} />}
        </>
      )}
      <LostModal opened={!!lost} onClose={() => setLost(null)} onConfirm={(reason, comment) => {
        if (lost) move(lost.dealId, lost.stageId, reason, comment);
        setLost(null);
      }} />
    </>
  );
}
