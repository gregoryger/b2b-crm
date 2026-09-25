import { ActionIcon, Button, Group, NumberInput, Select, Table, Text, TextInput, Tooltip } from '@mantine/core';
import { IconPlus, IconTrash } from '@tabler/icons-react';
import { useProducts } from '@/api/hooks';
import type { DealLine } from '@/api/types';
import { money } from '@/lib/format';

export const lineTotal = (l: DealLine) => (Number(l.quantity) || 0) * (Number(l.price) || 0) * (1 - (Number(l.discount_percent) || 0) / 100);

/** Табличный редактор позиций: товары/услуги из каталога с ценами и скидками */
export default function LinesEditor({ lines, onChange, currency = 'RUB', readOnly, vatRate }: {
  lines: DealLine[]; onChange: (l: DealLine[]) => void; currency?: string; readOnly?: boolean; vatRate?: number;
}) {
  const { data: products } = useProducts();
  const productOptions = (products ?? []).filter((p) => p.is_active).map((p) => ({
    value: String(p.id), label: `${p.name} — ${money(p.price, p.currency)}`,
  }));
  const set = (i: number, patch: Partial<DealLine>) => onChange(lines.map((l, idx) => (idx === i ? { ...l, ...patch } : l)));
  const add = () => onChange([...lines, { product_id: null, name: '', quantity: 1, unit: 'шт.', price: 0, discount_percent: 0 }]);
  const pick = (i: number, id: string | null) => {
    const p = products?.find((x) => String(x.id) === id);
    if (p) set(i, { product_id: p.id, name: p.name, unit: p.unit, price: p.price, description: p.description });
    else set(i, { product_id: null });
  };
  const total = lines.reduce((s, l) => s + lineTotal(l), 0);
  const vat = vatRate ? (total * vatRate) / (100 + vatRate) : 0;

  return (
    <>
      <Table.ScrollContainer minWidth={820}>
        <Table verticalSpacing={6} highlightOnHover={false}>
          <Table.Thead>
            <Table.Tr>
              <Table.Th>Товар / услуга</Table.Th>
              <Table.Th w={90}>Кол-во</Table.Th>
              <Table.Th w={80}>Ед.</Table.Th>
              <Table.Th w={140}>Цена</Table.Th>
              <Table.Th w={90}>Скидка, %</Table.Th>
              <Table.Th w={140} ta="right">Сумма</Table.Th>
              {!readOnly && <Table.Th w={40} />}
            </Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {lines.map((l, i) => (
              <Table.Tr key={i}>
                <Table.Td>
                  {readOnly ? (
                    <Text size="sm">{l.name}</Text>
                  ) : (
                    <>
                      <Select size="xs" placeholder="Из каталога…" data={productOptions} searchable clearable
                        value={l.product_id ? String(l.product_id) : null} onChange={(v) => pick(i, v)} mb={4}
                        aria-label="Товар из каталога" />
                      <TextInput size="xs" placeholder="Наименование" value={l.name} aria-label="Наименование"
                        onChange={(e) => set(i, { name: e.currentTarget.value })} error={!l.name.trim()} />
                    </>
                  )}
                </Table.Td>
                <Table.Td>
                  {readOnly ? l.quantity : <NumberInput size="xs" min={0.001} decimalScale={3} value={l.quantity}
                    onChange={(v) => set(i, { quantity: Number(v) || 0 })} hideControls aria-label="Количество" />}
                </Table.Td>
                <Table.Td>
                  {readOnly ? l.unit : <TextInput size="xs" value={l.unit} onChange={(e) => set(i, { unit: e.currentTarget.value })}
                    aria-label="Единица" />}
                </Table.Td>
                <Table.Td>
                  {readOnly ? money(l.price, currency, 2) : <NumberInput size="xs" min={0} decimalScale={2} thousandSeparator=" "
                    value={l.price} onChange={(v) => set(i, { price: Number(v) || 0 })} hideControls aria-label="Цена" />}
                </Table.Td>
                <Table.Td>
                  {readOnly ? `${l.discount_percent}%` : <NumberInput size="xs" min={0} max={100} value={l.discount_percent}
                    onChange={(v) => set(i, { discount_percent: Number(v) || 0 })} hideControls aria-label="Скидка" />}
                </Table.Td>
                <Table.Td ta="right">
                  <Text size="sm" fw={500}>{money(lineTotal(l), currency, 2)}</Text>
                </Table.Td>
                {!readOnly && (
                  <Table.Td>
                    <Tooltip label="Удалить строку">
                      <ActionIcon variant="subtle" color="red" onClick={() => onChange(lines.filter((_, idx) => idx !== i))}
                        aria-label="Удалить строку">
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Table.Td>
                )}
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      <Group justify="space-between" mt="sm" align="flex-start">
        {!readOnly ? <Button size="xs" variant="light" leftSection={<IconPlus size={14} />} onClick={add}>Добавить позицию</Button> : <span />}
        <div style={{ textAlign: 'right' }}>
          <Text fw={700} size="lg">Итого: {money(total, currency, 2)}</Text>
          {!!vatRate && <Text size="xs" c="dimmed">в т.ч. НДС {vatRate}%: {money(vat, currency, 2)}</Text>}
        </div>
      </Group>
    </>
  );
}
