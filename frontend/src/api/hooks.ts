import { useMutation, useQuery, useQueryClient, UseQueryOptions } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from './client';
import type { CustomField, DictItem, Product, ProposalTemplate, Stage, UserRef } from './types';

export function useApi<T>(key: unknown[], url: string | null, params?: Record<string, unknown>,
  options?: Partial<UseQueryOptions<T>>) {
  return useQuery<T>({
    queryKey: [...key, params],
    queryFn: async () => (await api.get<T>(url!, { params, paramsSerializer: { indexes: null } })).data,
    enabled: url !== null,
    ...options,
  });
}

/** Мутация с автоматическим уведомлением и инвалидацией кэша */
export function useApiMutation<TVars = any, TResult = any>(
  fn: (vars: TVars) => Promise<TResult>,
  opts: { invalidate?: unknown[][]; success?: string | ((r: TResult) => string); onSuccess?: (r: TResult) => void } = {},
) {
  const qc = useQueryClient();
  return useMutation<TResult, unknown, TVars>({
    mutationFn: fn,
    onSuccess: (r) => {
      opts.invalidate?.forEach((k) => qc.invalidateQueries({ queryKey: k }));
      if (opts.success) notifyOk(typeof opts.success === 'function' ? opts.success(r) : opts.success);
      opts.onSuccess?.(r);
    },
    onError: (e) => notifyError(e),
  });
}

const LONG = { staleTime: 5 * 60_000 };

export const useDictionaries = (kind?: string) =>
  useApi<DictItem[]>(['dictionaries'], '/dictionaries', kind ? { kind } : undefined, LONG);

export function useDict(kind: string, activeOnly = true) {
  const q = useApi<DictItem[]>(['dictionaries'], '/dictionaries', undefined, LONG);
  const items = (q.data ?? []).filter((d) => d.kind === kind && (!activeOnly || d.is_active));
  return { ...q, items, options: items.map((d) => ({ value: String(d.id), label: d.name })) };
}

export const useStages = () => useApi<Stage[]>(['stages'], '/stages', undefined, LONG);

export function useUsers(role?: string) {
  const q = useApi<UserRef[]>(['users-lookup'], '/users/lookup', role ? { role } : undefined, LONG);
  return { ...q, options: (q.data ?? []).map((u) => ({ value: String(u.id), label: u.full_name })) };
}

export const useProducts = () => useApi<Product[]>(['products'], '/products', undefined, LONG);
export const useCustomFields = (entity: string) =>
  useApi<CustomField[]>(['custom-fields', entity], '/custom-fields', { entity }, LONG);
export const useTemplates = () => useApi<ProposalTemplate[]>(['templates'], '/proposal-templates', undefined, LONG);

export function useSettings() {
  return useApi<Record<string, any>>(['settings'], '/settings', undefined, LONG);
}
