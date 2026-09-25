import { useState } from 'react';
import { ActionIcon, Badge, Button, Card, ColorSwatch, Group, NumberInput, Select, Stack, Switch, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { IconArrowDown, IconArrowUp, IconPlus, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError } from '@/api/client';
import { useStages } from '@/api/hooks';
import type { Stage } from '@/api/types';

const COLORS = ['gray', 'blue', 'cyan', 'teal', 'green', 'lime', 'yellow', 'orange', 'red', 'pink', 'grape', 'violet', 'indigo'];
const KINDS = [{ value: 'open', label: 'В работе' }, { value: 'won', label: 'Успех' }, { value: 'lost', label: 'Отказ' }];

export default function PipelineAdmin() {
  const qc = useQueryClient();
  const { data } = useStages();
  const [name, setName] = useState('');
  const refresh = () => {
    qc.invalidateQueries({ queryKey: ['stages'] });
    qc.invalidateQueries({ queryKey: ['board'] });
  };
  const save = async (s: Stage, patch: Partial<Stage>) => {
    try {
      await api.patch(`/stages/${s.id}`, { ...s, ...patch });
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const move = async (idx: number, dir: -1 | 1) => {
    if (!data) return;
    const ids = data.map((s) => s.id);
    [ids[idx], ids[idx + dir]] = [ids[idx + dir], ids[idx]];
    await api.put('/stages/order', { ids }).catch(notifyError);
    refresh();
  };
  const add = async () => {
    if (!name.trim() || !data) return;
    const lastOpen = [...data].reverse().find((s) => s.kind === 'open');
    try {
      await api.post('/stages', { name, probability: 50, color: 'blue', kind: 'open', sort: (lastOpen?.sort ?? 0) + 5 });
      setName('');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const remove = async (s: Stage) => {
    try {
      await api.delete(`/stages/${s.id}`);
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  return (
    <Card>
      <Stack>
        <Text size="sm" c="dimmed">Этапы воронки и вероятность закрытия — используются для канбан-доски и прогноза выручки.</Text>
        <Table>
          <Table.Thead>
            <Table.Tr><Table.Th w={70} /><Table.Th>Этап</Table.Th><Table.Th w={130}>Вероятность, %</Table.Th><Table.Th w={150}>Тип</Table.Th><Table.Th w={170}>Цвет</Table.Th><Table.Th w={110}>Активен</Table.Th><Table.Th w={40} /></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data?.map((s, i) => (
              <Table.Tr key={s.id}>
                <Table.Td>
                  <Group gap={0}>
                    <ActionIcon variant="subtle" size="sm" disabled={i === 0} onClick={() => move(i, -1)} aria-label="Выше"><IconArrowUp size={14} /></ActionIcon>
                    <ActionIcon variant="subtle" size="sm" disabled={i === data.length - 1} onClick={() => move(i, 1)} aria-label="Ниже"><IconArrowDown size={14} /></ActionIcon>
                  </Group>
                </Table.Td>
                <Table.Td><TextInput defaultValue={s.name} aria-label="Название этапа" onBlur={(e) => e.currentTarget.value !== s.name && save(s, { name: e.currentTarget.value })} /></Table.Td>
                <Table.Td><NumberInput min={0} max={100} defaultValue={s.probability} aria-label="Вероятность" onBlur={(e) => save(s, { probability: Number(e.currentTarget.value) })} /></Table.Td>
                <Table.Td><Select data={KINDS} value={s.kind} allowDeselect={false} aria-label="Тип" onChange={(v) => save(s, { kind: v as Stage['kind'] })} /></Table.Td>
                <Table.Td>
                  <Select data={COLORS} value={s.color} allowDeselect={false} aria-label="Цвет" onChange={(v) => save(s, { color: v! })}
                    leftSection={<ColorSwatch size={14} color={`var(--mantine-color-${s.color}-6)`} />} />
                </Table.Td>
                <Table.Td><Switch checked={s.is_active} aria-label="Активен" onChange={(e) => save(s, { is_active: e.currentTarget.checked })} /></Table.Td>
                <Table.Td>
                  <Tooltip label="Удалить (только если на этапе нет сделок)">
                    <ActionIcon variant="subtle" color="red" onClick={() => remove(s)} aria-label="Удалить"><IconTrash size={16} /></ActionIcon>
                  </Tooltip>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        <Group>
          <TextInput placeholder="Название нового этапа" value={name} onChange={(e) => setName(e.currentTarget.value)} style={{ flex: 1 }} aria-label="Новый этап" />
          <Button leftSection={<IconPlus size={16} />} onClick={add} disabled={!name.trim()}>Добавить этап</Button>
        </Group>
        <Group gap="xs">
          {data?.filter((s) => s.is_active).map((s) => <Badge key={s.id} color={s.color}>{s.name} · {s.probability}%</Badge>)}
        </Group>
      </Stack>
    </Card>
  );
}
