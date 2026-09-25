export const ROLE_LABELS: Record<string, string> = {
  admin: 'Администратор',
  head: 'Руководитель',
  manager: 'Менеджер',
  marketer: 'Маркетолог',
};

export const COMPANY_STATUS: Record<string, { label: string; color: string }> = {
  prospect: { label: 'Потенциальный', color: 'blue' },
  active: { label: 'Активный клиент', color: 'teal' },
  inactive: { label: 'Неактивный', color: 'gray' },
  partner: { label: 'Партнёр', color: 'violet' },
};

export const LEAD_STATUS: Record<string, { label: string; color: string }> = {
  new: { label: 'Новый', color: 'blue' },
  in_progress: { label: 'В работе', color: 'yellow' },
  qualified: { label: 'Квалифицирован', color: 'teal' },
  rejected: { label: 'Отклонён', color: 'gray' },
};

export const DEAL_STATUS: Record<string, { label: string; color: string }> = {
  open: { label: 'В работе', color: 'blue' },
  won: { label: 'Успех', color: 'teal' },
  lost: { label: 'Отказ', color: 'red' },
};

export const CONTACT_ROLES: Record<string, string> = {
  decision_maker: 'ЛПР',
  influencer: 'Влияющий',
  technical: 'Технический специалист',
  other: 'Другое',
};

export const TASK_TYPES: Record<string, { label: string; color: string }> = {
  call: { label: 'Звонок', color: 'blue' },
  meeting: { label: 'Встреча', color: 'violet' },
  email: { label: 'Письмо', color: 'cyan' },
  proposal: { label: 'Подготовка КП', color: 'orange' },
  other: { label: 'Другое', color: 'gray' },
};

export const PRIORITIES: Record<string, { label: string; color: string }> = {
  low: { label: 'Низкий', color: 'gray' },
  medium: { label: 'Средний', color: 'blue' },
  high: { label: 'Высокий', color: 'red' },
};

export const PROPOSAL_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'gray' },
  sent: { label: 'Отправлено', color: 'blue' },
  viewed: { label: 'Просмотрено', color: 'cyan' },
  approved: { label: 'Согласовано', color: 'teal' },
  rejected: { label: 'Отклонено', color: 'red' },
};

export const INVOICE_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'gray' },
  issued: { label: 'Выставлен', color: 'blue' },
  partially_paid: { label: 'Частично оплачен', color: 'yellow' },
  paid: { label: 'Оплачен', color: 'teal' },
  canceled: { label: 'Отменён', color: 'gray' },
};

export const ACT_STATUS: Record<string, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'gray' },
  sent: { label: 'Отправлен', color: 'blue' },
  signed: { label: 'Подписан', color: 'teal' },
};

export const DOC_TYPES: Record<string, string> = {
  proposal: 'КП',
  contract: 'Договор',
  invoice: 'Счёт',
  act: 'Акт',
  presentation: 'Презентация',
  other: 'Другое',
};

export const REMINDERS = [
  { value: '', label: 'Без напоминания' },
  { value: '15', label: 'За 15 минут' },
  { value: '60', label: 'За 1 час' },
  { value: '1440', label: 'За 1 день' },
];

export const CURRENCIES = ['RUB', 'USD', 'EUR', 'CNY'];

export const AUDIT_ACTIONS: Record<string, string> = {
  login: 'Вход',
  login_failed: 'Неудачный вход',
  create: 'Создание',
  update: 'Изменение',
  delete: 'Удаление',
  amount_change: 'Изменение суммы',
  export: 'Экспорт',
  import: 'Импорт',
  bulk_assign: 'Передача ответственному',
  user_create: 'Новый пользователь',
  user_update: 'Изменение пользователя',
  user_block: 'Блокировка',
  role_change: 'Смена роли',
  password_reset: 'Сброс пароля',
  password_change: 'Смена пароля',
  '2fa_enabled': 'Включена 2FA',
  '2fa_disabled': 'Отключена 2FA',
  '2fa_reset': 'Сброс 2FA',
  lead_convert: 'Конвертация лида',
  lead_reject: 'Отклонение лида',
  settings_change: 'Настройки',
  price_change: 'Изменение цены',
  proposal_send: 'Отправка КП',
  invoice_create: 'Счёт',
  invoice_cancel: 'Отмена счёта',
  payment_add: 'Оплата',
  payment_delete: 'Удаление оплаты',
  act_create: 'Акт',
  export_1c: 'Выгрузка в 1С',
  api_key_create: 'API-ключ',
  api_key_revoke: 'Отзыв API-ключа',
  file_delete: 'Удаление файла',
  dictionary_create: 'Справочник',
  dictionary_delete: 'Справочник',
  custom_field_create: 'Доп. поле',
  custom_field_delete: 'Доп. поле',
};
