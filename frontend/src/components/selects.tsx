import { useEffect, useMemo, useState } from 'react';
import { Select, SelectProps } from '@mantine/core';
import { useDebouncedValue } from '@mantine/hooks';
import { keepPreviousData } from '@tanstack/react-query';
import { useApi, useDict, useStages, useUsers } from '@/api/hooks';
import type { CompanyShort, Contact, Page } from '@/api/types';

type Base = Omit<SelectProps, 'data' | 'value' | 'onChange'> & {
  value?: number | null;
  onChange?: (v: number | null) => void;
};

const toStr = (v: number | null | undefined) => (v ? String(v) : null);
const toNum = (v: string | null) => (v ? Number(v) : null);

export function UserSelect({ value, onChange, role, ...rest }: Base & { role?: string }) {
  const { options } = useUsers(role);
  return <Select searchable clearable data={options} value={toStr(value)} onChange={(v) => onChange?.(toNum(v))}
    nothingFoundMessage="Не найдено" {...rest} />;
}

export function DictSelect({ kind, value, onChange, ...rest }: Base & { kind: string }) {
  const { options } = useDict(kind);
  return <Select searchable clearable data={options} value={toStr(value)} onChange={(v) => onChange?.(toNum(v))}
    nothingFoundMessage="Не найдено" {...rest} />;
}

export function StageSelect({ value, onChange, openOnly, ...rest }: Base & { openOnly?: boolean }) {
  const { data } = useStages();
  const options = (data ?? [])
    .filter((s) => s.is_active && (!openOnly || s.kind === 'open'))
    .map((s) => ({ value: String(s.id), label: `${s.name} · ${s.probability}%` }));
  return <Select data={options} value={toStr(value)} onChange={(v) => onChange?.(toNum(v))} {...rest} />;
}

const companyLabel = (c: CompanyShort) => (c.inn ? `${c.name} (ИНН ${c.inn})` : c.name);

/** Выбор компании с поиском по названию / ИНН */
export function CompanySelect({ value, onChange, initial, ...rest }: Base & { initial?: CompanyShort | null }) {
  const [search, setSearch] = useState('');
  const [debounced] = useDebouncedValue(search, 250);
  const [known, setKnown] = useState<CompanyShort | null>(initial ?? null);
  // Mantine подставляет подпись выбранного значения в поле поиска — её не отправляем как запрос,
  // иначе список пустеет, подпись меняется и поле начинает «мигать»
  const selectedLabel = known && value === known.id ? companyLabel(known) : null;
  const query = debounced && debounced !== selectedLabel ? debounced : undefined;
  const { data } = useApi<Page<CompanyShort>>(['companies-lookup'], '/companies', {
    q: query, page_size: 20, sort: 'name',
  }, { placeholderData: keepPreviousData });
  useEffect(() => {
    if (initial) setKnown(initial);
  }, [initial]);
  const options = useMemo(() => {
    const items = data?.items ?? [];
    const list = items.map((c) => ({ value: String(c.id), label: companyLabel(c) }));
    if (known && !items.some((c) => c.id === known.id)) list.unshift({ value: String(known.id), label: companyLabel(known) });
    return list;
  }, [data, known]);
  return (
    <Select
      searchable
      clearable
      data={options}
      value={toStr(value)}
      onChange={(v) => {
        const item = data?.items.find((c) => String(c.id) === v);
        if (item) setKnown(item);
        onChange?.(toNum(v));
      }}
      onSearchChange={setSearch}
      filter={({ options: o }) => o}
      nothingFoundMessage="Компания не найдена"
      placeholder="Начните вводить название или ИНН"
      {...rest}
    />
  );
}

export function ContactSelect({ value, onChange, companyId, ...rest }: Base & { companyId?: number | null }) {
  const { data } = useApi<Page<Contact>>(['contacts-lookup', companyId], companyId ? '/contacts' : null,
    { company_id: companyId, page_size: 100 });
  const options = (data?.items ?? []).map((c) => ({
    value: String(c.id), label: c.position ? `${c.full_name} — ${c.position}` : c.full_name,
  }));
  return <Select searchable clearable data={options} value={toStr(value)} onChange={(v) => onChange?.(toNum(v))}
    disabled={!companyId} placeholder={companyId ? 'Выберите контакт' : 'Сначала выберите компанию'}
    nothingFoundMessage="Нет контактов" {...rest} />;
}
