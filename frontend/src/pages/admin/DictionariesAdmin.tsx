import { useState } from 'react';
import { ActionIcon, Badge, Button, Card, Group, NavLink, Grid, Stack, Switch, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useDictionaries } from '@/api/hooks';

const KINDS = [
  { key: 'industry', label: 'Отрасли' },
  { key: 'region', label: 'Регионы' },
  { key: 'client_type', label: 'Типы клиентов' },
  { key: 'lead_source', label: 'Источники лидов' },
  { key: 'loss_reason', label: 'Причины отказа' },
];

export default function DictionariesAdmin() {
  const qc = useQueryClient();
  const [kind, setKind] = useState('industry');
  const [name, setName] = useState('');
  const { data } = useDictionaries();
  const items = (data ?? []).filter((d) => d.kind === kind);
  const refresh = () => qc.invalidateQueries({ queryKey: ['dictionaries'] });

  const add = async () => {
    if (!name.trim()) return;
    try {
      await api.post('/dictionaries', { kind, name: name.trim(), sort: (items.length + 1) * 10 });
      setName('');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const update = async (id: number, patch: object) => {
    try {
      await api.patch(`/dictionaries/${id}`, patch);
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const remove = async (id: number) => {
    try {
      const { data: r } = await api.delete(`/dictionaries/${id}`);
      notifyOk(r.detail);
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };

  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 3 }}>
        <Card p="xs">
          {KINDS.map((k) => (
            <NavLink key={k.key} label={k.label} active={kind === k.key} onClick={() => setKind(k.key)} style={{ borderRadius: 8 }}
              rightSection={<Badge size="xs" variant="light">{(data ?? []).filter((d) => d.kind === k.key).length}</Badge>} />
          ))}
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 9 }}>
        <Card>
          <Stack>
            <Group>
              <TextInput placeholder="Новое значение" value={name} onChange={(e) => setName(e.currentTarget.value)} style={{ flex: 1 }}
                onKeyDown={(e) => e.key === 'Enter' && add()} aria-label="Новое значение" />
              <Button leftSection={<IconPlus size={16} />} onClick={add} disabled={!name.trim()}>Добавить</Button>
            </Group>
            <Table>
              <Table.Tbody>
                {items.map((d) => (
                  <Table.Tr key={d.id}>
                    <Table.Td>
                      <TextInput variant="unstyled" defaultValue={d.name} aria-label="Название"
                        onBlur={(e) => e.currentTarget.value !== d.name && update(d.id, { name: e.currentTarget.value })} />
                    </Table.Td>
                    <Table.Td w={120}>{d.code && <Badge variant="outline" size="sm">{d.code}</Badge>}</Table.Td>
                    <Table.Td w={140}>
                      <Switch size="sm" label={d.is_active ? 'Активно' : 'Скрыто'} checked={d.is_active}
                        onChange={(e) => update(d.id, { is_active: e.currentTarget.checked })} />
                    </Table.Td>
                    <Table.Td w={50}>
                      {!d.code && (
                        <Tooltip label="Удалить">
                          <ActionIcon variant="subtle" color="red" onClick={() => remove(d.id)} aria-label="Удалить"><IconTrash size={16} /></ActionIcon>
                        </Tooltip>
                      )}
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
            <Text size="xs" c="dimmed">Используемые значения при удалении скрываются из выбора, но сохраняются в карточках. Системные источники (с кодом) удалить нельзя.</Text>
          </Stack>
        </Card>
      </Grid.Col>
    </Grid>
  );
}
