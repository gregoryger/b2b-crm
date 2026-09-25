import { Navigate, Route, Routes, useLocation, useNavigate } from 'react-router-dom';
import { Tabs } from '@mantine/core';
import { useAuth } from '@/auth/AuthContext';
import { PageHeader } from '@/components/ui';
import AuditAdmin from './AuditAdmin';
import DictionariesAdmin from './DictionariesAdmin';
import FieldsAdmin from './FieldsAdmin';
import IntegrationsAdmin from './IntegrationsAdmin';
import MarketingAdmin from './MarketingAdmin';
import PipelineAdmin from './PipelineAdmin';
import ProductsAdmin from './ProductsAdmin';
import SettingsAdmin from './SettingsAdmin';
import TemplatesAdmin from './TemplatesAdmin';
import UsersAdmin from './UsersAdmin';

const SECTIONS = [
  { path: 'users', label: 'Пользователи и роли', perm: 'users.manage', el: <UsersAdmin /> },
  { path: 'pipeline', label: 'Воронка', perm: 'pipeline.edit', el: <PipelineAdmin /> },
  { path: 'dictionaries', label: 'Справочники', perm: 'dictionaries.edit', el: <DictionariesAdmin /> },
  { path: 'products', label: 'Продукты и услуги', perm: 'products.edit', el: <ProductsAdmin /> },
  { path: 'fields', label: 'Доп. поля', perm: 'custom_fields.edit', el: <FieldsAdmin /> },
  { path: 'templates', label: 'Шаблоны КП', perm: 'templates.edit', el: <TemplatesAdmin /> },
  { path: 'marketing', label: 'Маркетинговые бюджеты', perm: 'marketing.edit', el: <MarketingAdmin /> },
  { path: 'integrations', label: 'Интеграции', perm: 'integrations.manage', el: <IntegrationsAdmin /> },
  { path: 'settings', label: 'Компания и настройки', perm: 'settings.manage', el: <SettingsAdmin /> },
  { path: 'audit', label: 'Журнал аудита', perm: 'audit.view', el: <AuditAdmin /> },
];

export default function AdminPage() {
  const { can } = useAuth();
  const navigate = useNavigate();
  const location = useLocation();
  const sections = SECTIONS.filter((s) => can(s.perm));
  if (!sections.length) return <Navigate to="/" replace />;
  const current = location.pathname.split('/')[2] || sections[0].path;
  return (
    <>
      <PageHeader title="Администрирование" subtitle="Пользователи, справочники, настройки и интеграции" />
      <Tabs value={current} onChange={(v) => navigate(`/admin/${v}`)} mb="lg">
        <Tabs.List style={{ flexWrap: 'wrap' }}>
          {sections.map((s) => <Tabs.Tab key={s.path} value={s.path}>{s.label}</Tabs.Tab>)}
        </Tabs.List>
      </Tabs>
      <Routes>
        <Route index element={<Navigate to={sections[0].path} replace />} />
        {sections.map((s) => <Route key={s.path} path={s.path} element={s.el} />)}
        <Route path="*" element={<Navigate to={sections[0].path} replace />} />
      </Routes>
    </>
  );
}
