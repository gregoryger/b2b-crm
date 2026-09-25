import { useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { Badge, Group, Loader, Text } from '@mantine/core';
import { Spotlight } from '@mantine/spotlight';
import { useDebouncedValue } from '@mantine/hooks';
import { IconBuilding, IconBriefcase, IconSearch, IconTarget, IconUser } from '@tabler/icons-react';
import { useApi } from '@/api/hooks';

interface Hit {
  id: number;
  title: string;
  subtitle: string;
}
type Result = Record<'companies' | 'contacts' | 'deals' | 'leads', Hit[]>;

const GROUPS = [
  { key: 'companies', label: 'Компании', one: 'Компания', icon: IconBuilding, url: '/companies' },
  { key: 'contacts', label: 'Контакты', one: 'Контакт', icon: IconUser, url: '/contacts' },
  { key: 'deals', label: 'Сделки', one: 'Сделка', icon: IconBriefcase, url: '/deals' },
  { key: 'leads', label: 'Лиды', one: 'Лид', icon: IconTarget, url: '/leads' },
] as const;

/** Глобальный поиск: «/» или Ctrl+K. Название, ИНН, телефон, ФИО, email */
export default function GlobalSearch() {
  const [query, setQuery] = useState('');
  const [debounced] = useDebouncedValue(query.trim(), 250);
  const navigate = useNavigate();
  const { data, isFetching } = useApi<Result>(['search', debounced], debounced.length >= 2 ? '/search' : null,
    { q: debounced });
  const total = data ? GROUPS.reduce((s, g) => s + data[g.key].length, 0) : 0;

  return (
    <Spotlight.Root query={query} onQueryChange={setQuery} shortcut={['mod + K', '/']} scrollable maxHeight={480}>
      <Spotlight.Search placeholder="Поиск: компания, ИНН, телефон, ФИО, сделка…"
        leftSection={isFetching ? <Loader size={16} /> : <IconSearch size={18} stroke={1.5} />} />
      <Spotlight.ActionsList>
        {debounced.length < 2 && <Spotlight.Empty>Введите минимум 2 символа</Spotlight.Empty>}
        {debounced.length >= 2 && data && total === 0 && <Spotlight.Empty>Ничего не найдено</Spotlight.Empty>}
        {data &&
          GROUPS.filter((g) => data[g.key].length).map((g) => (
            <Spotlight.ActionsGroup key={g.key} label={g.label}>
              {data[g.key].map((h) => (
                <Spotlight.Action key={`${g.key}${h.id}`} onClick={() => navigate(`${g.url}/${h.id}`)}
                  leftSection={<g.icon size={18} stroke={1.5} />}>
                  <Group justify="space-between" w="100%" wrap="nowrap">
                    <div style={{ minWidth: 0 }}>
                      <Text size="sm" truncate>
                        {h.title}
                      </Text>
                      {h.subtitle && (
                        <Text size="xs" c="dimmed" truncate>
                          {h.subtitle}
                        </Text>
                      )}
                    </div>
                    <Badge size="xs" variant="outline" color="gray">
                      {g.one}
                    </Badge>
                  </Group>
                </Spotlight.Action>
              ))}
            </Spotlight.ActionsGroup>
          ))}
      </Spotlight.ActionsList>
    </Spotlight.Root>
  );
}
