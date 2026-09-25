import { useState } from 'react';
import { ActionIcon, Button, Card, Group, NumberInput, Stack, Table, Text } from '@mantine/core';
import { MonthPickerInput } from '@mantine/dates';
import { IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi, useDict } from '@/api/hooks';
import { DictSelect } from '@/components/selects';
import { dayjs, money, toISODate } from '@/lib/format';

interface Spend { id: number; source_id: number; month: string; amount: number; comment: string | null }

/** Расходы на каналы привлечения — для расчёта стоимости лида и продажи в отчёте «Источники лидов» */
export default function MarketingAdmin() {
  const qc = useQueryClient();
  const { data } = useApi<Spend[]>(['spend'], '/marketing-spend');
  const src = useDict('lead_source', false);
  const [source, setSource] = useState<number | null>(null);
  const [month, setMonth] = useState<Date | null>(dayjs().startOf('month').toDate());
  const [amount, setAmount] = useState<number | string>('');
  const save = async () => {
    try {
      await api.put('/marketing-spend', { source_id: source, month: toISODate(month), amount: Number(amount) });
      notifyOk('Бюджет сохранён');
      setAmount('');
      qc.invalidateQueries({ queryKey: ['spend'] });
    } catch (e) {
      notifyError(e);
    }
  };
  const name = (id: number) => src.items.find((s) => s.id === id)?.name ?? '—';
  return (
    <Card>
      <Stack>
        <Text size="sm" c="dimmed">Укажите расходы на каждый канал по месяцам — в отчётах появятся стоимость лида (CPL), стоимость продажи и ROI.</Text>
        <Group align="flex-end">
          <DictSelect kind="lead_source" label="Источник" value={source} onChange={setSource} w={240} />
          <MonthPickerInput label="Месяц" value={month} onChange={setMonth} valueFormat="MMMM YYYY" w={200} />
          <NumberInput label="Сумма, ₽" value={amount} onChange={setAmount} thousandSeparator=" " min={0} w={180} />
          <Button onClick={save} disabled={!source || !month || amount === ''}>Сохранить</Button>
        </Group>
        <Table>
          <Table.Thead><Table.Tr><Table.Th>Месяц</Table.Th><Table.Th>Источник</Table.Th><Table.Th ta="right">Бюджет</Table.Th><Table.Th w={40} /></Table.Tr></Table.Thead>
          <Table.Tbody>
            {data?.slice(0, 60).map((s) => (
              <Table.Tr key={s.id}>
                <Table.Td style={{ textTransform: 'capitalize' }}>{dayjs(s.month).format('MMMM YYYY')}</Table.Td>
                <Table.Td>{name(s.source_id)}</Table.Td>
                <Table.Td ta="right">{money(s.amount)}</Table.Td>
                <Table.Td>
                  <ActionIcon variant="subtle" color="red" aria-label="Удалить" onClick={async () => {
                    await api.delete(`/marketing-spend/${s.id}`).catch(notifyError);
                    qc.invalidateQueries({ queryKey: ['spend'] });
                  }}><IconTrash size={16} /></ActionIcon>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Stack>
    </Card>
  );
}
