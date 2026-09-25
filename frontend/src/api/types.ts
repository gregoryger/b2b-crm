export type Role = 'admin' | 'head' | 'manager' | 'marketer';

export interface Ref {
  id: number;
  name: string;
}
export interface UserRef {
  id: number;
  full_name: string;
  email?: string | null;
}
export interface Page<T> {
  items: T[];
  total: number;
  page: number;
  page_size: number;
  pages: number;
}

export interface Me {
  id: number;
  email: string;
  full_name: string;
  position: string | null;
  phone: string | null;
  role: Role;
  department: string | null;
  permissions: string[];
  must_change_password: boolean;
  onboarding_done: boolean;
  notify_push: boolean;
  notify_email: boolean;
  notify_telegram: boolean;
  telegram_linked: boolean;
  totp_enabled: boolean;
  sip_extension: string | null;
}

export interface UserFull {
  id: number;
  email: string;
  full_name: string;
  position: string | null;
  phone: string | null;
  role: Role;
  department: string | null;
  is_active: boolean;
  last_login: string | null;
  created_at: string;
  sip_extension: string | null;
  totp_enabled: boolean;
}

export interface DictItem {
  id: number;
  kind: string;
  name: string;
  code: string | null;
  sort: number;
  is_active: boolean;
}

export interface Stage {
  id: number;
  name: string;
  sort: number;
  probability: number;
  color: string;
  kind: 'open' | 'won' | 'lost';
  is_active: boolean;
}

export interface Product {
  id: number;
  name: string;
  sku: string | null;
  category: string | null;
  unit: string;
  price: number;
  cost: number;
  currency: string;
  vat_rate: number;
  description: string | null;
  is_active: boolean;
}

export interface CustomField {
  id: number;
  entity: 'company' | 'contact' | 'deal' | 'lead';
  key: string;
  label: string;
  field_type: 'text' | 'number' | 'date' | 'select' | 'checkbox';
  options: string[] | null;
  required: boolean;
  sort: number;
  is_active: boolean;
}

export interface CompanyShort {
  id: number;
  name: string;
  inn?: string | null;
}

export interface Company {
  id: number;
  name: string;
  full_name: string | null;
  inn: string | null;
  kpp: string | null;
  ogrn: string | null;
  legal_address: string | null;
  actual_address: string | null;
  bank_name: string | null;
  bik: string | null;
  account: string | null;
  corr_account: string | null;
  industry: Ref | null;
  region: Ref | null;
  client_type: Ref | null;
  source: Ref | null;
  manager: UserRef | null;
  status: 'prospect' | 'active' | 'inactive' | 'partner';
  phone: string | null;
  email: string | null;
  website: string | null;
  description: string | null;
  custom_fields: Record<string, unknown>;
  last_contact_at: string | null;
  created_at: string;
  updated_at: string;
  total_revenue: number;
  open_deals: number;
}

export interface ContactShort {
  id: number;
  full_name: string;
  position?: string | null;
  email?: string | null;
  phone_mobile?: string | null;
}

export interface Contact {
  id: number;
  company: CompanyShort | null;
  owner: UserRef | null;
  last_name: string;
  first_name: string;
  middle_name: string | null;
  full_name: string;
  position: string | null;
  phone_mobile: string | null;
  phone_work: string | null;
  email: string | null;
  telegram: string | null;
  whatsapp: string | null;
  role_in_deal: string | null;
  notes: string | null;
  custom_fields: Record<string, unknown>;
  created_at: string;
}

export interface Lead {
  id: number;
  title: string;
  source: Ref | null;
  status: 'new' | 'in_progress' | 'qualified' | 'rejected';
  reject_reason: Ref | null;
  reject_comment: string | null;
  assignee: UserRef | null;
  company_name: string | null;
  inn: string | null;
  contact_name: string | null;
  contact_position: string | null;
  phone: string | null;
  email: string | null;
  message: string | null;
  estimated_amount: number | null;
  utm_source: string | null;
  utm_medium: string | null;
  utm_campaign: string | null;
  custom_fields: Record<string, unknown>;
  company_id: number | null;
  contact_id: number | null;
  deal_id: number | null;
  first_response_at: string | null;
  qualified_at: string | null;
  created_at: string;
  updated_at: string;
}

export interface StageRef {
  id: number;
  name: string;
  color: string;
  kind: 'open' | 'won' | 'lost';
  probability: number;
}

export interface DealLine {
  id?: number;
  product_id: number | null;
  name: string;
  description?: string | null;
  quantity: number;
  unit: string;
  price: number;
  discount_percent: number;
  total?: number;
}

export interface Deal {
  is_stale?: boolean;
  id: number;
  title: string;
  company: CompanyShort | null;
  contact: ContactShort | null;
  owner: UserRef | null;
  stage: StageRef;
  lead_id: number | null;
  amount: number;
  currency: string;
  probability: number;
  close_date: string | null;
  status: 'open' | 'won' | 'lost';
  closed_at: string | null;
  lost_reason: Ref | null;
  lost_comment: string | null;
  description: string | null;
  custom_fields: Record<string, unknown>;
  stage_changed_at: string;
  created_at: string;
  updated_at: string;
}

export interface DealDetail extends Deal {
  products: DealLine[];
  contacts: { contact: ContactShort; role: string | null }[];
  members: { user: UserRef; role: string | null }[];
}

export interface BoardColumn {
  stage: StageRef;
  count: number;
  amount: number;
  weighted: number;
  deals: Deal[];
}

export interface RelatedRef {
  type: 'deal' | 'company' | 'contact' | 'lead';
  id: number;
  name: string;
}

export interface Task {
  id: number;
  title: string;
  type: 'call' | 'meeting' | 'email' | 'proposal' | 'other';
  priority: 'low' | 'medium' | 'high';
  status: 'open' | 'done' | 'canceled';
  description: string | null;
  result: string | null;
  assignee: UserRef | null;
  author_id: number | null;
  due_at: string;
  duration_minutes: number;
  deal_id: number | null;
  company_id: number | null;
  contact_id: number | null;
  lead_id: number | null;
  reminder_minutes: number | null;
  completed_at: string | null;
  created_at: string;
  related: RelatedRef[];
  is_overdue: boolean;
}

export interface Activity {
  id: number;
  type: string;
  title: string;
  body: string | null;
  user: UserRef | null;
  object_type: string;
  object_id: number;
  company_id: number | null;
  contact_id: number | null;
  deal_id: number | null;
  lead_id: number | null;
  meta: Record<string, any>;
  occurred_at: string;
}

export interface FileItem {
  id: number;
  deal_id: number | null;
  company_id: number | null;
  doc_type: string;
  name: string;
  content_type: string | null;
  size: number;
  uploader: UserRef | null;
  created_at: string;
}

export interface EmailItem {
  id: number;
  direction: 'in' | 'out';
  status: string;
  subject: string;
  body: string | null;
  from_email: string | null;
  to_email: string;
  opened_at: string | null;
  open_count: number;
  sent_at: string | null;
  created_at: string;
}

export interface ProposalTemplate {
  id: number;
  name: string;
  industry_id: number | null;
  description: string | null;
  intro_text: string;
  terms_text: string;
  footer_text: string;
  accent_color: string;
  default_items: { product_id: number | null; quantity?: number }[];
  is_active: boolean;
}

export interface Proposal {
  id: number;
  number: string;
  title: string;
  deal_id: number | null;
  company: CompanyShort | null;
  contact: ContactShort | null;
  template_id: number | null;
  owner: UserRef | null;
  status: 'draft' | 'sent' | 'viewed' | 'approved' | 'rejected';
  currency: string;
  vat_rate: number;
  valid_until: string | null;
  intro_text: string;
  terms_text: string;
  total: number;
  sent_to: string | null;
  sent_at: string | null;
  viewed_at: string | null;
  decided_at: string | null;
  client_comment: string | null;
  created_at: string;
  public_url: string | null;
}

export interface ProposalDetail extends Proposal {
  items: DealLine[];
}

export interface Invoice {
  id: number;
  number: string;
  deal_id: number | null;
  company: CompanyShort | null;
  owner: UserRef | null;
  issued_at: string;
  due_date: string;
  currency: string;
  vat_rate: number;
  items: DealLine[];
  amount: number;
  paid_amount: number;
  status: 'draft' | 'issued' | 'partially_paid' | 'paid' | 'canceled';
  paid_at: string | null;
  comment: string | null;
  exported_1c_at: string | null;
  created_at: string;
  is_overdue: boolean;
  debt: number;
  payments?: { id: number; amount: number; paid_at: string; comment: string | null }[];
}

export interface Act {
  currency: string;
  id: number;
  number: string;
  invoice_id: number | null;
  deal_id: number | null;
  company: CompanyShort | null;
  act_date: string;
  amount: number;
  vat_rate: number;
  status: 'draft' | 'sent' | 'signed';
  exported_1c_at: string | null;
  created_at: string;
}

export interface Notification {
  id: number;
  kind: string;
  title: string;
  body: string | null;
  link: string | null;
  is_read: boolean;
  created_at: string;
}

export interface ReportColumn {
  key: string;
  label: string;
  type: 'text' | 'int' | 'float' | 'money' | 'pct' | 'date';
}
export interface Report {
  title: string;
  subtitle?: string;
  columns: ReportColumn[];
  rows: Record<string, any>[];
  totals: Record<string, any> | null;
  aging?: Record<string, number>;
}
