import { createContext, ReactNode, useCallback, useContext, useMemo, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { CompanyModal, DealModal, LeadModal, TaskDefaults, TaskModal } from './forms';

type Kind = 'deal' | 'lead' | 'company' | 'task';

interface QuickCreateApi {
  open: (kind: Kind, defaults?: Record<string, any>) => void;
}

const Ctx = createContext<QuickCreateApi>({ open: () => undefined });

/** Быстрое создание сущностей из любого места (кнопка «+», горячие клавиши) */
export function QuickCreateProvider({ children }: { children: ReactNode }) {
  const [kind, setKind] = useState<Kind | null>(null);
  const [defaults, setDefaults] = useState<Record<string, any>>({});
  const navigate = useNavigate();
  const open = useCallback((k: Kind, d: Record<string, any> = {}) => {
    setDefaults(d);
    setKind(k);
  }, []);
  const close = () => setKind(null);
  const value = useMemo(() => ({ open }), [open]);
  return (
    <Ctx.Provider value={value}>
      {children}
      <DealModal opened={kind === 'deal'} onClose={close} defaults={defaults}
        onSaved={(d) => navigate(`/deals/${d.id}`)} />
      <LeadModal opened={kind === 'lead'} onClose={close} onSaved={(l) => navigate(`/leads/${l.id}`)} />
      <CompanyModal opened={kind === 'company'} onClose={close} onSaved={(c) => navigate(`/companies/${c.id}`)} />
      <TaskModal opened={kind === 'task'} onClose={close} defaults={defaults as TaskDefaults} />
    </Ctx.Provider>
  );
}

export const useQuickCreate = () => useContext(Ctx);
