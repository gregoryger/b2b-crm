import { ReactNode } from 'react';
import { Group, Table, Text, UnstyledButton } from '@mantine/core';
import { IconChevronDown, IconChevronUp, IconSelector } from '@tabler/icons-react';

/** Заголовок таблицы с сортировкой: sort = "field" | "-field" */
export default function SortTh({ field, sort, onSort, children, ta }: {
  field: string; sort: string; onSort: (s: string) => void; children: ReactNode; ta?: 'right' | 'left';
}) {
  const active = sort.replace('-', '') === field;
  const desc = sort.startsWith('-');
  const Icon = !active ? IconSelector : desc ? IconChevronDown : IconChevronUp;
  return (
    <Table.Th ta={ta}>
      <UnstyledButton onClick={() => onSort(active && !desc ? `-${field}` : active && desc ? field : `-${field}`)}
        aria-label={`Сортировать: ${typeof children === 'string' ? children : field}`}>
        <Group gap={4} wrap="nowrap" justify={ta === 'right' ? 'flex-end' : 'flex-start'}>
          <Text size="sm" fw={600}>
            {children}
          </Text>
          <Icon size={14} opacity={active ? 1 : 0.4} />
        </Group>
      </UnstyledButton>
    </Table.Th>
  );
}
