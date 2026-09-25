import { Group, Select } from '@mantine/core';
import { DatePickerInput } from '@mantine/dates';
import { dayjs, toISODate } from '@/lib/format';

export interface Period {
  preset: string;
  from: string;
  to: string;
}

export function periodFromPreset(preset: string): Period {
  const t = dayjs();
  const q = Math.floor(t.month() / 3) * 3;
  const map: Record<string, [dayjs.Dayjs, dayjs.Dayjs]> = {
    month: [t.startOf('month'), t],
    prev_month: [t.subtract(1, 'month').startOf('month'), t.subtract(1, 'month').endOf('month')],
    quarter: [t.month(q).startOf('month'), t],
    half: [t.subtract(5, 'month').startOf('month'), t],
    year: [t.startOf('year'), t],
    last12: [t.subtract(11, 'month').startOf('month'), t],
  };
  const [a, b] = map[preset] ?? map.month;
  return { preset, from: a.format('YYYY-MM-DD'), to: b.format('YYYY-MM-DD') };
}

const PRESETS = [
  { value: 'month', label: 'Этот месяц' },
  { value: 'prev_month', label: 'Прошлый месяц' },
  { value: 'quarter', label: 'Этот квартал' },
  { value: 'half', label: 'Полгода' },
  { value: 'year', label: 'С начала года' },
  { value: 'last12', label: '12 месяцев' },
  { value: 'custom', label: 'Произвольный период' },
];

export default function PeriodPicker({ value, onChange }: { value: Period; onChange: (p: Period) => void }) {
  return (
    <Group gap="xs" wrap="nowrap">
      <Select w={190} data={PRESETS} value={value.preset} allowDeselect={false} aria-label="Период"
        onChange={(v) => (v === 'custom' ? onChange({ ...value, preset: 'custom' }) : onChange(periodFromPreset(v!)))} />
      {value.preset === 'custom' && (
        <DatePickerInput type="range" w={240} valueFormat="DD.MM.YYYY" aria-label="Даты"
          value={[new Date(value.from), new Date(value.to)]}
          onChange={([a, b]) => a && b && onChange({ preset: 'custom', from: toISODate(a)!, to: toISODate(b)! })} />
      )}
    </Group>
  );
}
