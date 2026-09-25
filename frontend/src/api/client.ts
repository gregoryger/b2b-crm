import axios, { AxiosError, AxiosRequestConfig } from 'axios';
import { notifications } from '@mantine/notifications';

const ACCESS = 'crm.access';
const REFRESH = 'crm.refresh';

export const tokens = {
  get access() {
    return localStorage.getItem(ACCESS);
  },
  get refresh() {
    return localStorage.getItem(REFRESH);
  },
  set(access: string, refresh: string) {
    localStorage.setItem(ACCESS, access);
    localStorage.setItem(REFRESH, refresh);
  },
  clear() {
    localStorage.removeItem(ACCESS);
    localStorage.removeItem(REFRESH);
  },
};

export const api = axios.create({ baseURL: '/api/v1' });

api.interceptors.request.use((config) => {
  const t = tokens.access;
  if (t) config.headers.Authorization = `Bearer ${t}`;
  return config;
});

let refreshing: Promise<string | null> | null = null;

async function refreshAccess(): Promise<string | null> {
  const rt = tokens.refresh;
  if (!rt) return null;
  try {
    const { data } = await axios.post('/api/v1/auth/refresh', { refresh_token: rt });
    tokens.set(data.access_token, data.refresh_token);
    return data.access_token;
  } catch {
    tokens.clear();
    return null;
  }
}

api.interceptors.response.use(
  (r) => r,
  async (error: AxiosError) => {
    const original = error.config as AxiosRequestConfig & { _retry?: boolean };
    if (error.response?.status === 401 && original && !original._retry && !original.url?.includes('/auth/')) {
      original._retry = true;
      refreshing = refreshing ?? refreshAccess().finally(() => (refreshing = null));
      const newToken = await refreshing;
      if (newToken) {
        original.headers = { ...(original.headers || {}), Authorization: `Bearer ${newToken}` };
        return api(original);
      }
      window.dispatchEvent(new Event('crm:logout'));
    }
    if (error.response?.status === 429) {
      notifications.show({ color: 'orange', title: 'Слишком много запросов', message: 'Подождите минуту' });
    }
    return Promise.reject(error);
  },
);

export function errorMessage(e: unknown): string {
  const err = e as AxiosError<{ detail?: string | { msg: string }[] }>;
  const detail = err?.response?.data?.detail;
  if (typeof detail === 'string') return detail;
  if (Array.isArray(detail)) return detail.map((d) => d.msg).join('; ');
  if (err?.response?.status === 403) return 'Недостаточно прав';
  if (err?.response?.status && err.response.status >= 500) return 'Ошибка сервера. Повторите попытку позже';
  if (err?.message === 'Network Error') return 'Нет связи с сервером';
  return 'Что-то пошло не так';
}

export function notifyError(e: unknown, title = 'Ошибка') {
  notifications.show({ color: 'red', title, message: errorMessage(e) });
}

export function notifyOk(message: string, title?: string) {
  notifications.show({ color: 'teal', title, message });
}

/** Скачивание файла (PDF, Excel) с авторизацией */
export async function download(url: string, params?: Record<string, unknown>, fallbackName = 'file') {
  try {
    const res = await api.get(url, { params, responseType: 'blob', paramsSerializer: { indexes: null } });
    const disp = (res.headers['content-disposition'] as string) || '';
    const m = /filename\*=UTF-8''([^;]+)/.exec(disp) || /filename="?([^";]+)"?/.exec(disp);
    const name = m ? decodeURIComponent(m[1]) : fallbackName;
    const href = URL.createObjectURL(res.data);
    const a = document.createElement('a');
    a.href = href;
    a.download = name;
    document.body.appendChild(a);
    a.click();
    a.remove();
    setTimeout(() => URL.revokeObjectURL(href), 5000);
  } catch (e) {
    notifyError(e, 'Не удалось скачать файл');
  }
}

/** Открыть PDF в новой вкладке (с авторизацией) */
export async function openPdf(url: string) {
  const win = window.open('', '_blank');
  try {
    const res = await api.get(url, { responseType: 'blob' });
    const href = URL.createObjectURL(res.data);
    if (win) win.location.href = href;
    else window.location.href = href;
  } catch (e) {
    win?.close();
    notifyError(e, 'Не удалось сформировать PDF');
  }
}
