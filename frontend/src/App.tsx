import { lazy, ReactNode, Suspense } from 'react';
import { Navigate, Route, Routes, useLocation } from 'react-router-dom';
import { Center, Loader } from '@mantine/core';
import { useAuth } from './auth/AuthContext';
import AppLayout from './components/AppLayout';
import LoginPage from './pages/LoginPage';

const Dashboard = lazy(() => import('./pages/DashboardPage'));
const Leads = lazy(() => import('./pages/leads/LeadsPage'));
const LeadCard = lazy(() => import('./pages/leads/LeadCard'));
const Companies = lazy(() => import('./pages/companies/CompaniesPage'));
const CompanyCard = lazy(() => import('./pages/companies/CompanyCard'));
const Contacts = lazy(() => import('./pages/contacts/ContactsPage'));
const ContactCard = lazy(() => import('./pages/contacts/ContactCard'));
const Deals = lazy(() => import('./pages/deals/DealsPage'));
const DealCard = lazy(() => import('./pages/deals/DealCard'));
const Tasks = lazy(() => import('./pages/tasks/TasksPage'));
const Calendar = lazy(() => import('./pages/tasks/CalendarPage'));
const Proposals = lazy(() => import('./pages/proposals/ProposalsPage'));
const ProposalEditor = lazy(() => import('./pages/proposals/ProposalEditor'));
const Finance = lazy(() => import('./pages/finance/FinancePage'));
const Reports = lazy(() => import('./pages/reports/ReportsPage'));
const Admin = lazy(() => import('./pages/admin/AdminPage'));
const Profile = lazy(() => import('./pages/ProfilePage'));
const Help = lazy(() => import('./pages/HelpPage'));
const PublicProposal = lazy(() => import('./pages/PublicProposalPage'));

const Spinner = () => (
  <Center h="60vh">
    <Loader />
  </Center>
);

function RequireAuth({ children }: { children: ReactNode }) {
  const { user, loading } = useAuth();
  const location = useLocation();
  if (loading) return <Spinner />;
  if (!user) return <Navigate to="/login" state={{ from: location }} replace />;
  return <>{children}</>;
}

function RequirePerm({ perm, children }: { perm: string; children: ReactNode }) {
  const { can } = useAuth();
  if (!can(perm)) return <Navigate to="/" replace />;
  return <>{children}</>;
}

export default function App() {
  return (
    <Suspense fallback={<Spinner />}>
      <Routes>
        <Route path="/login" element={<LoginPage />} />
        <Route path="/p/:token" element={<PublicProposal />} />
        <Route
          element={
            <RequireAuth>
              <AppLayout />
            </RequireAuth>
          }
        >
          <Route index element={<Dashboard />} />
          <Route path="leads" element={<Leads />} />
          <Route path="leads/:id" element={<LeadCard />} />
          <Route path="companies" element={<Companies />} />
          <Route path="companies/:id" element={<CompanyCard />} />
          <Route path="contacts" element={<Contacts />} />
          <Route path="contacts/:id" element={<ContactCard />} />
          <Route path="deals" element={<RequirePerm perm="deals.view"><Deals /></RequirePerm>} />
          <Route path="deals/:id" element={<RequirePerm perm="deals.view"><DealCard /></RequirePerm>} />
          <Route path="tasks" element={<Tasks />} />
          <Route path="calendar" element={<Calendar />} />
          <Route path="proposals" element={<RequirePerm perm="proposals.edit"><Proposals /></RequirePerm>} />
          <Route path="proposals/:id" element={<RequirePerm perm="proposals.edit"><ProposalEditor /></RequirePerm>} />
          <Route path="finance" element={<RequirePerm perm="finance.view"><Finance /></RequirePerm>} />
          <Route path="reports" element={<RequirePerm perm="analytics.view"><Reports /></RequirePerm>} />
          <Route path="admin/*" element={<Admin />} />
          <Route path="profile" element={<Profile />} />
          <Route path="help" element={<Help />} />
          <Route path="*" element={<Navigate to="/" replace />} />
        </Route>
      </Routes>
    </Suspense>
  );
}
