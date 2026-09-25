import { Dispatch, SetStateAction, useEffect, useState } from 'react';
import { useLocation } from 'react-router-dom';
import { useAuth } from '@/auth/AuthContext';

/** Сохраняет выборку при переходе в карточку; состояние разделено по сотрудникам. */
export function useListState<T>(name: string, initial: T): [T, Dispatch<SetStateAction<T>>] {
  const { user } = useAuth();
  const { pathname } = useLocation();
  const key = `crm.list.${user?.id}.${pathname}.${name}`;
  const [value, setValue] = useState<T>(() => {
    try {
      const raw = sessionStorage.getItem(key);
      if (raw === null) return initial;
      const saved = JSON.parse(raw);
      if (Array.isArray(initial)) return Array.isArray(saved) ? saved : initial;
      return saved === null || initial === null || typeof saved === typeof initial ? saved : initial;
    } catch { return initial; }
  });
  useEffect(() => { try { sessionStorage.setItem(key, JSON.stringify(value)); } catch { /* storage unavailable */ } }, [key, value]);
  return [value, setValue];
}
