import { useState } from 'react';
import { Badge, Button, Card, Group, Modal, NumberInput, Select, SimpleGrid, Stack, Switch, Table, Text, Textarea, TextInput } from '@mantine/core';
import { useForm } from '@mantine/form';
import { IconPlus } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useProducts } from '@/api/hooks';
import type { Product } from '@/api/types';
import { money, pct } from '@/lib/format';
import { CURRENCIES } from '@/lib/labels';

function ProductModal({ product, opened, onClose }: { product: Product | null; opened: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const form = useForm({
    initialValues: {
      name: product?.name ?? '', sku: product?.sku ?? '', category: product?.category ?? '', unit: product?.unit ?? 'шт.',
      price: product?.price ?? 0, cost: product?.cost ?? 0, currency: product?.currency ?? 'RUB',
      vat_rate: String(product?.vat_rate ?? 20), description: product?.description ?? '', is_active: product?.is_active ?? true,
    },
    validate: { name: (v: string) => (v.trim() ? null : 'Укажите название') },
  });
  const submit = form.onSubmit(async (v) => {
    try {
      const body = { ...v, vat_rate: Number(v.vat_rate) };
      if (product) await api.patch(`/products/${product.id}`, body);
      else await api.post('/products', body);
      notifyOk('Сохранено');
      qc.invalidateQueries({ queryKey: ['products'] });
      onClose();
    } catch (e) {
      notifyError(e);
    }
  });
  return (
    <Modal opened={opened} onClose={onClose} title={product ? 'Продукт' : 'Новый продукт / услуга'} size="lg">
      <form onSubmit={submit}>
        <Stack>
          <TextInput label="Название" withAsterisk {...form.getInputProps('name')} />
          <SimpleGrid cols={{ base: 1, sm: 3 }}>
            <TextInput label="Артикул" {...form.getInputProps('sku')} />
            <TextInput label="Категория" {...form.getInputProps('category')} />
            <TextInput label="Единица" {...form.getInputProps('unit')} />
            <NumberInput label="Цена" thousandSeparator=" " min={0} decimalScale={2} {...form.getInputProps('price')} />
            <NumberInput label="Себестоимость" description="для расчёта маржи" thousandSeparator=" " min={0} decimalScale={2} {...form.getInputProps('cost')} />
            <Select label="Валюта" data={CURRENCIES} allowDeselect={false} {...form.getInputProps('currency')} />
            <Select label="НДС" data={[{ value: '20', label: '20%' }, { value: '10', label: '10%' }, { value: '0', label: 'Без НДС' }]}
              allowDeselect={false} {...form.getInputProps('vat_rate')} />
          </SimpleGrid>
          <Textarea label="Описание (попадёт в КП)" autosize minRows={2} {...form.getInputProps('description')} />
          <Switch label="Доступен для выбора" {...form.getInputProps('is_active', { type: 'checkbox' })} />
          <Group justify="flex-end"><Button variant="default" onClick={onClose}>Отмена</Button><Button type="submit">Сохранить</Button></Group>
        </Stack>
      </form>
    </Modal>
  );
}

export default function ProductsAdmin() {
  const { data } = useProducts();
  const [editing, setEditing] = useState<Product | null>(null);
  const [open, setOpen] = useState(false);
  return (
    <Card>
      <Group justify="space-between" mb="md">
        <Text size="sm" c="dimmed">Каталог используется в сделках, КП и счетах. Изменение цены фиксируется в журнале аудита.</Text>
        <Button leftSection={<IconPlus size={16} />} onClick={() => { setEditing(null); setOpen(true); }}>Продукт</Button>
      </Group>
      <Table.ScrollContainer minWidth={800}>
        <Table>
          <Table.Thead>
            <Table.Tr><Table.Th>Название</Table.Th><Table.Th>Категория</Table.Th><Table.Th ta="right">Цена</Table.Th><Table.Th ta="right">Себестоимость</Table.Th><Table.Th ta="right">Маржа</Table.Th><Table.Th>Статус</Table.Th></Table.Tr>
          </Table.Thead>
          <Table.Tbody>
            {data?.map((p) => (
              <Table.Tr key={p.id} className="clickable-row" onClick={() => { setEditing(p); setOpen(true); }} opacity={p.is_active ? 1 : 0.5}>
                <Table.Td><Text size="sm" fw={500}>{p.name}</Text><Text size="xs" c="dimmed">{p.sku} · {p.unit}</Text></Table.Td>
                <Table.Td>{p.category}</Table.Td>
                <Table.Td ta="right">{money(p.price, p.currency)}</Table.Td>
                <Table.Td ta="right">{money(p.cost, p.currency)}</Table.Td>
                <Table.Td ta="right">{p.price ? pct(((p.price - p.cost) / p.price) * 100) : '—'}</Table.Td>
                <Table.Td>{p.is_active ? <Badge color="teal">Активен</Badge> : <Badge color="gray">Скрыт</Badge>}</Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      </Table.ScrollContainer>
      {open && <ProductModal product={editing} opened={open} onClose={() => setOpen(false)} />}
    </Card>
  );
}
