import { createContext, ReactNode, useCallback, useContext, useEffect, useMemo, useState } from 'react';
import { useQueryClient } from '@tanstack/react-query';
import { api, tokens } from '@/api/client';
import type { Me } from '@/api/types';

interface LoginResult {
  twoFactorToken?: string;
}

interface AuthState {
  user: Me | null;
  loading: boolean;
  login: (email: string, password: string) => Promise<LoginResult>;
  verify2fa: (token: string, code: string) => Promise<void>;
  logout: () => Promise<void>;
  reload: () => Promise<void>;
  can: (perm: string) => boolean;
}

const Ctx = createContext<AuthState | null>(null);

export function AuthProvider({ children }: { children: ReactNode }) {
  const [user, setUser] = useState<Me | null>(null);
  const [loading, setLoading] = useState(true);
  const qc = useQueryClient();

  const reload = useCallback(async () => {
    if (!tokens.access && !tokens.refresh) {
      setUser(null);
      setLoading(false);
      return;
    }
    try {
      const { data } = await api.get<Me>('/auth/me');
      setUser(data);
    } catch {
      tokens.clear();
      setUser(null);
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    reload();
    const onLogout = () => {
      tokens.clear();
      setUser(null);
      qc.clear();
    };
    window.addEventListener('crm:logout', onLogout);
    return () => window.removeEventListener('crm:logout', onLogout);
  }, [reload, qc]);

  const login = useCallback(
    async (email: string, password: string): Promise<LoginResult> => {
      const { data } = await api.post('/auth/login', { email, password });
      if (data.two_factor_required) return { twoFactorToken: data.two_factor_token };
      tokens.set(data.access_token, data.refresh_token);
      await reload();
      return {};
    },
    [reload],
  );

  const verify2fa = useCallback(
    async (token: string, code: string) => {
      const { data } = await api.post('/auth/2fa', { token, code });
      tokens.set(data.access_token, data.refresh_token);
      await reload();
    },
    [reload],
  );

  const logout = useCallback(async () => {
    const rt = tokens.refresh;
    if (rt) await api.post('/auth/logout', { refresh_token: rt }).catch(() => undefined);
    tokens.clear();
    setUser(null);
    qc.clear();
  }, [qc]);

  const can = useCallback((perm: string) => !!user?.permissions.includes(perm), [user]);

  const value = useMemo(
    () => ({ user, loading, login, verify2fa, logout, reload, can }),
    [user, loading, login, verify2fa, logout, reload, can],
  );
  return <Ctx.Provider value={value}>{children}</Ctx.Provider>;
}

export function useAuth(): AuthState {
  const ctx = useContext(Ctx);
  if (!ctx) throw new Error('useAuth outside AuthProvider');
  return ctx;
}
