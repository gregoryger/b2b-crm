import { Badge, Table, Text, Tooltip } from '@mantine/core';
import { useApi } from '@/api/hooks';
import type { EmailItem } from '@/api/types';
import { dateTime, smartDate } from '@/lib/format';
import { Empty } from './ui';

export default function EmailHistory(props: { company_id?: number; contact_id?: number; deal_id?: number; lead_id?: number }) {
  const { data } = useApi<EmailItem[]>(['emails', props], '/emails', props);
  if (!data?.length) return <Empty text="Переписки пока нет" />;
  return (
    <Table.ScrollContainer minWidth={600}>
      <Table>
        <Table.Thead>
          <Table.Tr>
            <Table.Th>Тема</Table.Th>
            <Table.Th>Кому / от кого</Table.Th>
            <Table.Th>Дата</Table.Th>
            <Table.Th>Статус</Table.Th>
          </Table.Tr>
        </Table.Thead>
        <Table.Tbody>
          {data.map((e) => (
            <Table.Tr key={e.id}>
              <Table.Td>
                <Tooltip label={e.body?.slice(0, 300)} multiline w={360} disabled={!e.body}>
                  <Text size="sm">
                    {e.direction === 'in' ? '← ' : '→ '}
                    {e.subject}
                  </Text>
                </Tooltip>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{e.direction === 'in' ? e.from_email : e.to_email}</Text>
              </Table.Td>
              <Table.Td>
                <Text size="sm">{smartDate(e.sent_at ?? e.created_at)}</Text>
              </Table.Td>
              <Table.Td>
                {e.direction === 'in' ? (
                  <Badge size="sm" color="cyan">Входящее</Badge>
                ) : e.opened_at ? (
                  <Tooltip label={`Открыто ${dateTime(e.opened_at)}, просмотров: ${e.open_count}`}>
                    <Badge size="sm" color="teal">Прочитано</Badge>
                  </Tooltip>
                ) : e.status === 'failed' ? (
                  <Badge size="sm" color="red">Ошибка</Badge>
                ) : (
                  <Badge size="sm" color="gray">{e.status === 'sent' ? 'Доставлено' : 'В очереди'}</Badge>
                )}
              </Table.Td>
            </Table.Tr>
          ))}
        </Table.Tbody>
      </Table>
    </Table.ScrollContainer>
  );
}
