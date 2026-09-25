import dayjs from 'dayjs';
import 'dayjs/locale/ru';
import relativeTime from 'dayjs/plugin/relativeTime';
import customParseFormat from 'dayjs/plugin/customParseFormat';
import isToday from 'dayjs/plugin/isToday';

dayjs.extend(relativeTime);
dayjs.extend(customParseFormat);
dayjs.extend(isToday);
dayjs.locale('ru');

export { dayjs };

const SYMBOLS: Record<string, string> = { RUB: '₽', USD: '$', EUR: '€', CNY: '¥' };

export function money(value: number | string | null | undefined, currency = 'RUB', digits = 0): string {
  const v = Number(value ?? 0);
  const s = v.toLocaleString('ru-RU', { minimumFractionDigits: digits, maximumFractionDigits: digits });
  return `${s} ${SYMBOLS[currency] ?? currency}`.trim();
}

/** Компактная запись крупных сумм: 1,2 млн ₽ */
export function moneyShort(value: number | null | undefined, currency = 'RUB'): string {
  const v = Number(value ?? 0);
  const abs = Math.abs(v);
  const sym = SYMBOLS[currency] ?? currency;
  if (abs >= 1e9) return `${(v / 1e9).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млрд ${sym}`;
  if (abs >= 1e6) return `${(v / 1e6).toLocaleString('ru-RU', { maximumFractionDigits: 1 })} млн ${sym}`;
  if (abs >= 1e3) return `${(v / 1e3).toLocaleString('ru-RU', { maximumFractionDigits: 0 })} тыс. ${sym}`;
  return money(v, currency);
}

export function num(value: number | null | undefined, digits = 0): string {
  return Number(value ?? 0).toLocaleString('ru-RU', { maximumFractionDigits: digits });
}

export function date(value: string | Date | null | undefined): string {
  return value ? dayjs(value).format('DD.MM.YYYY') : '—';
}

export function dateTime(value: string | Date | null | undefined): string {
  return value ? dayjs(value).format('DD.MM.YYYY HH:mm') : '—';
}

export function ago(value: string | null | undefined): string {
  return value ? dayjs(value).fromNow() : '—';
}

export function smartDate(value: string | null | undefined): string {
  if (!value) return '—';
  const d = dayjs(value);
  if (d.isToday()) return `сегодня, ${d.format('HH:mm')}`;
  if (d.isSame(dayjs().add(1, 'day'), 'day')) return `завтра, ${d.format('HH:mm')}`;
  if (d.isSame(dayjs().subtract(1, 'day'), 'day')) return `вчера, ${d.format('HH:mm')}`;
  return d.format(d.year() === dayjs().year() ? 'D MMM, HH:mm' : 'DD.MM.YYYY HH:mm');
}

export function fileSize(bytes: number): string {
  if (bytes < 1024) return `${bytes} Б`;
  if (bytes < 1024 * 1024) return `${(bytes / 1024).toFixed(0)} КБ`;
  return `${(bytes / 1024 / 1024).toFixed(1)} МБ`;
}

export function initials(name: string | null | undefined): string {
  if (!name) return '?';
  const p = name.split(' ').filter(Boolean);
  return ((p[0]?.[0] ?? '') + (p[1]?.[0] ?? '')).toUpperCase();
}

export function plural(n: number, forms: [string, string, string]): string {
  const a = Math.abs(n) % 100;
  const b = a % 10;
  if (a > 10 && a < 20) return forms[2];
  if (b > 1 && b < 5) return forms[1];
  if (b === 1) return forms[0];
  return forms[2];
}

export function pct(value: number | null | undefined): string {
  return value === null || value === undefined ? '—' : `${num(value, 1)}%`;
}

export function toISODate(d: Date | string | null | undefined): string | undefined {
  return d ? dayjs(d).format('YYYY-MM-DD') : undefined;
}
