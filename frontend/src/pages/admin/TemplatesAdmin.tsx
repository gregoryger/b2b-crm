import { useEffect, useState } from 'react';
import { Badge, Button, Card, ColorInput, Grid, Group, NavLink, Stack, Switch, Text, Textarea, TextInput } from '@mantine/core';
import { IconPlus } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi, useTemplates } from '@/api/hooks';
import type { ProposalTemplate } from '@/api/types';
import { DictSelect } from '@/components/selects';

const EMPTY: Partial<ProposalTemplate> = { name: 'Новый шаблон', intro_text: '', terms_text: '', footer_text: '', accent_color: '#1c7ed6', is_active: true };

export default function TemplatesAdmin() {
  const qc = useQueryClient();
  const { data } = useTemplates();
  const { data: vars } = useApi<{ key: string; label: string }[]>(['kp-vars'], '/proposal-templates/variables');
  const [selected, setSelected] = useState<number | 'new' | null>(null);
  const [form, setForm] = useState<Partial<ProposalTemplate>>(EMPTY);
  useEffect(() => {
    if (selected === null && data?.length) setSelected(data[0].id);
  }, [data, selected]);
  useEffect(() => {
    if (selected === 'new') setForm(EMPTY);
    else if (selected) setForm(data?.find((t) => t.id === selected) ?? EMPTY);
  }, [selected, data]);
  const set = (p: Partial<ProposalTemplate>) => setForm({ ...form, ...p });
  const save = async () => {
    try {
      const body = { ...form, default_items: form.default_items ?? [] };
      if (selected === 'new') {
        const { data: t } = await api.post('/proposal-templates', body);
        setSelected(t.id);
      } else await api.patch(`/proposal-templates/${selected}`, body);
      notifyOk('Шаблон сохранён');
      qc.invalidateQueries({ queryKey: ['templates'] });
    } catch (e) {
      notifyError(e);
    }
  };
  return (
    <Grid>
      <Grid.Col span={{ base: 12, md: 3 }}>
        <Card p="xs">
          {data?.map((t) => (
            <NavLink key={t.id} label={t.name} active={selected === t.id} onClick={() => setSelected(t.id)} style={{ borderRadius: 8 }}
              rightSection={!t.is_active ? <Badge size="xs" color="gray">off</Badge> : undefined} />
          ))}
          <Button variant="subtle" fullWidth leftSection={<IconPlus size={16} />} mt="xs" onClick={() => setSelected('new')}>Новый шаблон</Button>
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, md: 9 }}>
        <Card>
          <Stack>
            <Group grow>
              <TextInput label="Название шаблона" value={form.name ?? ''} onChange={(e) => set({ name: e.currentTarget.value })} />
              <DictSelect kind="industry" label="Для отрасли" value={form.industry_id ?? null} onChange={(v) => set({ industry_id: v })} placeholder="Для всех" />
              <ColorInput label="Фирменный цвет" value={form.accent_color} onChange={(v) => set({ accent_color: v })} />
            </Group>
            <Textarea label="Описание" autosize value={form.description ?? ''} onChange={(e) => set({ description: e.currentTarget.value })} />
            <Textarea label="Вступительный текст" autosize minRows={4} value={form.intro_text} onChange={(e) => set({ intro_text: e.currentTarget.value })} />
            <Textarea label="Условия" autosize minRows={4} value={form.terms_text} onChange={(e) => set({ terms_text: e.currentTarget.value })} />
            <Textarea label="Подпись (внизу КП)" autosize value={form.footer_text} onChange={(e) => set({ footer_text: e.currentTarget.value })} />
            <Text size="xs" c="dimmed">
              Переменные: {vars?.map((v) => v.key).join(', ')}
            </Text>
            <Group justify="space-between">
              <Switch label="Активен" checked={form.is_active ?? true} onChange={(e) => set({ is_active: e.currentTarget.checked })} />
              <Button onClick={save}>Сохранить шаблон</Button>
            </Group>
          </Stack>
        </Card>
      </Grid.Col>
    </Grid>
  );
}
