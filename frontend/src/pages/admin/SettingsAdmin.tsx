import { useEffect, useState } from 'react';
import { Button, Card, ColorInput, FileButton, Grid, Group, Image, MultiSelect, NumberInput, Radio, SimpleGrid, Stack, Text, TextInput, Title } from '@mantine/core';
import { IconUpload } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useSettings, useUsers } from '@/api/hooks';

export default function SettingsAdmin() {
  const qc = useQueryClient();
  const { data } = useSettings();
  const users = useUsers('manager');
  const [profile, setProfile] = useState<Record<string, string>>({});
  const [dist, setDist] = useState<{ mode: string; user_ids: number[] }>({ mode: 'round_robin', user_ids: [] });
  const [rates, setRates] = useState<Record<string, number>>({});
  const [logoVer, setLogoVer] = useState(Date.now());
  useEffect(() => {
    if (data) {
      setProfile(data.company_profile ?? {});
      setDist(data.lead_distribution ?? { mode: 'round_robin', user_ids: [] });
      setRates(data.currencies ?? {});
    }
  }, [data]);
  const save = async (key: string, value: object, msg = 'Настройки сохранены') => {
    try {
      await api.put(`/settings/${key}`, value);
      notifyOk(msg);
      qc.invalidateQueries({ queryKey: ['settings'] });
    } catch (e) {
      notifyError(e);
    }
  };
  const upload = async (file: File | null) => {
    if (!file) return;
    const fd = new FormData();
    fd.append('file', file);
    try {
      await api.post('/settings/logo', fd);
      setLogoVer(Date.now());
      notifyOk('Логотип загружен — он появится в КП и счетах');
      qc.invalidateQueries({ queryKey: ['settings'] });
    } catch (e) {
      notifyError(e);
    }
  };
  const f = (key: string, label: string, span = 1) => (
    <TextInput key={key} label={label} value={profile[key] ?? ''} style={{ gridColumn: `span ${span}` }}
      onChange={(e) => setProfile({ ...profile, [key]: e.currentTarget.value })} />
  );
  return (
    <Grid>
      <Grid.Col span={{ base: 12, lg: 8 }}>
        <Card>
          <Title order={5} mb="xs">Реквизиты вашей компании</Title>
          <Text size="sm" c="dimmed" mb="md">Используются в коммерческих предложениях, счетах и актах.</Text>
          <SimpleGrid cols={{ base: 1, sm: 2 }}>
            {f('name', 'Краткое наименование')}{f('full_name', 'Полное наименование')}
            {f('inn', 'ИНН')}{f('kpp', 'КПП')}{f('ogrn', 'ОГРН')}{f('address', 'Адрес')}
            {f('phone', 'Телефон')}{f('email', 'Email')}{f('website', 'Сайт')}
            {f('bank_name', 'Банк')}{f('bik', 'БИК')}{f('account', 'Расчётный счёт')}{f('corr_account', 'Корр. счёт')}
            {f('director', 'Руководитель (подпись)')}{f('accountant', 'Бухгалтер (подпись)')}
            <ColorInput label="Фирменный цвет" value={profile.accent_color ?? '#1c7ed6'} onChange={(v) => setProfile({ ...profile, accent_color: v })} />
          </SimpleGrid>
          <Group justify="flex-end" mt="md"><Button onClick={() => save('company_profile', profile)}>Сохранить реквизиты</Button></Group>
        </Card>
      </Grid.Col>
      <Grid.Col span={{ base: 12, lg: 4 }}>
        <Stack>
          <Card>
            <Title order={5} mb="sm">Логотип</Title>
            {data?.company_profile?.logo_key ? (
              <Image src={`/api/v1/public/logo?v=${logoVer}`} h={60} fit="contain" mb="sm" alt="Логотип" />
            ) : <Text size="sm" c="dimmed" mb="sm">Не загружен</Text>}
            <FileButton onChange={upload} accept="image/png,image/jpeg,image/svg+xml">
              {(props) => <Button variant="default" leftSection={<IconUpload size={16} />} {...props}>Загрузить (PNG, JPG, SVG)</Button>}
            </FileButton>
          </Card>
          <Card>
            <Title order={5} mb="sm">Распределение лидов</Title>
            <Radio.Group value={dist.mode} onChange={(v) => setDist({ ...dist, mode: v })}>
              <Stack gap="xs">
                <Radio value="round_robin" label="По очереди (round-robin)" />
                <Radio value="least_loaded" label="Наименее загруженному менеджеру" />
                <Radio value="off" label="Вручную (руководитель назначает)" />
              </Stack>
            </Radio.Group>
            <MultiSelect label="Участвуют в распределении" placeholder="Все менеджеры" mt="sm" data={users.options}
              value={(dist.user_ids ?? []).map(String)} onChange={(v) => setDist({ ...dist, user_ids: v.map(Number) })} clearable />
            <Button mt="md" onClick={() => save('lead_distribution', dist)}>Сохранить</Button>
          </Card>
          <Card>
            <Title order={5} mb="sm">Курсы валют для отчётов</Title>
            <Stack gap="xs">
              {Object.entries(rates).filter(([k]) => k !== 'RUB').map(([k, v]) => (
                <NumberInput key={k} label={`1 ${k} = ₽`} value={v} decimalScale={4} min={0}
                  onChange={(x) => setRates({ ...rates, [k]: Number(x) })} />
              ))}
            </Stack>
            <Button mt="md" onClick={() => save('currencies', rates)}>Сохранить</Button>
          </Card>
        </Stack>
      </Grid.Col>
    </Grid>
  );
}
