import { Checkbox, NumberInput, Select, SimpleGrid, TextInput } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { useCustomFields } from '@/api/hooks';
import { date as fmtDate, num, toISODate } from '@/lib/format';
import { Field } from './ui';

type Values = Record<string, unknown>;

export function CustomFieldsInputs({ entity, value, onChange }: {
  entity: string; value: Values; onChange: (v: Values) => void;
}) {
  const { data } = useCustomFields(entity);
  const fields = (data ?? []).filter((f) => f.is_active);
  if (!fields.length) return null;
  const set = (key: string, v: unknown) => onChange({ ...value, [key]: v });
  return (
    <SimpleGrid cols={{ base: 1, sm: 2 }}>
      {fields.map((f) => {
        const v = value?.[f.key];
        const common = { label: f.label, withAsterisk: f.required, key: f.key };
        switch (f.field_type) {
          case 'number':
            return <NumberInput {...common} value={(v as number) ?? ''} thousandSeparator=" "
              onChange={(x) => set(f.key, x === '' ? null : x)} />;
          case 'date':
            return <DatePickerInput {...common} clearable valueFormat="DD.MM.YYYY"
              value={v ? new Date(String(v)) : null} onChange={(d) => set(f.key, toISODate(d) ?? null)} />;
          case 'select':
            return <Select {...common} clearable data={f.options ?? []} value={(v as string) ?? null}
              onChange={(x) => set(f.key, x)} />;
          case 'checkbox':
            return <Checkbox key={f.key} mt="xl" label={f.label} checked={!!v}
              onChange={(e) => set(f.key, e.currentTarget.checked)} />;
          default:
            return <TextInput {...common} value={(v as string) ?? ''} onChange={(e) => set(f.key, e.currentTarget.value)} />;
        }
      })}
    </SimpleGrid>
  );
}

export function CustomFieldsView({ entity, value }: { entity: string; value: Values }) {
  const { data } = useCustomFields(entity);
  const fields = (data ?? []).filter((f) => f.is_active);
  if (!fields.length) return null;
  return (
    <>
      {fields.map((f) => {
        const v = value?.[f.key];
        let text: string | null = null;
        if (v !== null && v !== undefined && v !== '') {
          if (f.field_type === 'checkbox') text = v ? 'Да' : 'Нет';
          else if (f.field_type === 'date') text = fmtDate(String(v));
          else if (f.field_type === 'number') text = num(Number(v), 2);
          else text = String(v);
        }
        return (
          <Field key={f.key} label={f.label}>
            {text}
          </Field>
        );
      })}
    </>
  );
}
