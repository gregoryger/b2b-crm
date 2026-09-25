import { useState } from 'react';
import { ActionIcon, Badge, Button, Card, Checkbox, Group, SegmentedControl, Select, Stack, Switch, Table, TagsInput, Text, TextInput } from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { modals } from '@mantine/modals';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { CustomField } from '@/api/types';

const ENTITIES = [{ value: 'company', label: 'Компании' }, { value: 'contact', label: 'Контакты' }, { value: 'deal', label: 'Сделки' }, { value: 'lead', label: 'Лиды' }];
const TYPES = [{ value: 'text', label: 'Текст' }, { value: 'number', label: 'Число' }, { value: 'date', label: 'Дата' }, { value: 'select', label: 'Список' }, { value: 'checkbox', label: 'Флажок' }];

export default function FieldsAdmin() {
  const qc = useQueryClient();
  const [entity, setEntity] = useState('company');
  const { data } = useApi<CustomField[]>(['custom-fields', entity], '/custom-fields', { entity });
  const [label, setLabel] = useState('');
  const [type, setType] = useState<string | null>('text');
  const [options, setOptions] = useState<string[]>([]);
  const [required, setRequired] = useState(false);
  const refresh = () => qc.invalidateQueries({ queryKey: ['custom-fields'] });
  const add = async () => {
    try {
      await api.post('/custom-fields', { entity, label, field_type: type, options: type === 'select' ? options : null, required,
        sort: ((data?.length ?? 0) + 1) * 10 });
      setLabel('');
      setOptions([]);
      setRequired(false);
      notifyOk('Поле добавлено');
      refresh();
    } catch (e) {
      notifyError(e);
    }
  };
  const update = async (f: CustomField, patch: Partial<CustomField>) => {
    await api.patch(`/custom-fields/${f.id}`, patch).catch(notifyError);
    refresh();
  };
  const remove = (f: CustomField) => modals.openConfirmModal({
    title: `Удалить поле «${f.label}»?`, labels: { confirm: 'Удалить', cancel: 'Отмена' }, confirmProps: { color: 'red' },
    children: <Text size="sm">Поле исчезнет из карточек. Рекомендуем вместо удаления отключить его.</Text>,
    onConfirm: async () => {
      await api.delete(`/custom-fields/${f.id}`).catch(notifyError);
      refresh();
    },
  });
  return (
    <Card>
      <Stack>
        <SegmentedControl data={ENTITIES} value={entity} onChange={setEntity} w="fit-content" />
        <Table>
          <Table.Thead>
            <Table.Tr><Table.Th>Название</Table.Th><Table.Th>Тип</Table.Th><Table.Th>Значения</Table.Th><Table.Th>Обязательное</Table.Th><Table.Th>Активно</Table.Th><Table.Th w={40} /></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data?.map((f) => (
              <Table.Tr key={f.id}>
                <Table.Td><Text size="sm" fw={500}>{f.label}</Text><Text size="xs" c="dimmed">{f.key}</Text></Table.Td>
                <Table.Td><Badge variant="outline">{TYPES.find((t) => t.value === f.field_type)?.label}</Badge></Table.Td>
                <Table.Td>
                  {f.field_type === 'select' && (
                    <TagsInput size="xs" value={f.options ?? []} onChange={(v) => update(f, { options: v })} aria-label="Значения списка" />
                  )}
                </Table.Td>
                <Table.Td><Checkbox checked={f.required} onChange={(e) => update(f, { required: e.currentTarget.checked })} aria-label="Обязательное" /></Table.Td>
                <Table.Td><Switch checked={f.is_active} onChange={(e) => update(f, { is_active: e.currentTarget.checked })} aria-label="Активно" /></Table.Td>
                <Table.Td><ActionIcon variant="subtle" color="red" onClick={() => remove(f)} aria-label="Удалить"><IconTrash size={16} /></ActionIcon></Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
        {!data?.length && <Text size="sm" c="dimmed">Дополнительных полей пока нет.</Text>}
        <Group align="flex-end">
          <TextInput label="Новое поле" placeholder="Например: Количество филиалов" value={label} onChange={(e) => setLabel(e.currentTarget.value)} w={280} />
          <Select label="Тип" data={TYPES} value={type} onChange={setType} allowDeselect={false} w={140} />
          {type === 'select' && <TagsInput label="Значения" placeholder="Введите и Enter" value={options} onChange={setOptions} w={280} />}
          <Checkbox label="Обязательное" checked={required} onChange={(e) => setRequired(e.currentTarget.checked)} mb={8} />
          <Button leftSection={<IconPlus size={16} />} onClick={add} disabled={!label.trim() || (type === 'select' && !options.length)}>Добавить</Button>
        </Group>
      </Stack>
    </Card>
  );
}
