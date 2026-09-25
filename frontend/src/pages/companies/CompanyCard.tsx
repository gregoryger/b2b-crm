import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  Anchor,
  Badge,
  Button,
  Card,
  Center,
  Grid,
  Group,
  Loader,
  Menu,
  SimpleGrid,
  Stack,
  Table,
  Tabs,
  Text,
  Title,
} from '@mantine/core';
import { modals } from '@mantine/modals';
import {
  IconArrowLeft,
  IconBriefcase,
  IconDots,
  IconEdit,
  IconFileText,
  IconMail,
  IconPlus,
  IconTrash,
  IconUserPlus,
} from '@tabler/icons-react';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Company, Contact, Deal, Invoice, Page, Proposal } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { CustomFieldsView } from '@/components/CustomFields';
import EmailHistory from '@/components/EmailHistory';
import EmailModal from '@/components/EmailModal';
import FilesPanel from '@/components/FilesPanel';
import { CompanyModal, ContactModal, DealModal } from '@/components/forms';
import TasksPanel from '@/components/TasksPanel';
import Timeline from '@/components/Timeline';
import { Empty, EntityLink, Field, Phone, StatusBadge } from '@/components/ui';
import { ago, date, money } from '@/lib/format';
import { COMPANY_STATUS, CONTACT_ROLES, DEAL_STATUS, INVOICE_STATUS, PROPOSAL_STATUS } from '@/lib/labels';

export default function CompanyCard() {
  const { id } = useParams();
  const cid = Number(id);
  const navigate = useNavigate();
  const { can } = useAuth();
  const [edit, setEdit] = useState(false);
  const [contactModal, setContactModal] = useState<{ open: boolean; contact?: Contact | null }>({ open: false });
  const [dealModal, setDealModal] = useState(false);
  const [emailTo, setEmailTo] = useState<string | null | undefined>(undefined);
  const { data: c, isLoading, error } = useApi<Company>(['company', cid], `/companies/${cid}`);
  const { data: contacts } = useApi<Page<Contact>>(['contacts', { company: cid }], '/contacts', { company_id: cid, page_size: 100 });
  const { data: deals } = useApi<Page<Deal>>(['deals', { company: cid }], can('deals.view') ? '/deals' : null,
    { company_id: cid, page_size: 100, sort: '-created_at' });
  const { data: proposals } = useApi<Page<Proposal>>(['proposals', { company: cid }], can('proposals.edit') ? '/proposals' : null,
    { company_id: cid, page_size: 50 });
  const { data: invoices } = useApi<Page<Invoice>>(['invoices', { company: cid }], can('finance.view') ? '/invoices' : null,
    { company_id: cid, page_size: 50 });

  if (isLoading) return <Center h="50vh"><Loader /></Center>;
  if (error || !c) return <Empty text="Компания не найдена или нет доступа" action={<Button onClick={() => navigate('/companies')}>К списку</Button>} />;

  const remove = () =>
    modals.openConfirmModal({
      title: 'Удалить компанию?',
      children: <Text size="sm">Компания «{c.name}» будет скрыта из базы. Действие фиксируется в журнале аудита.</Text>,
      labels: { confirm: 'Удалить', cancel: 'Отмена' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await api.delete(`/companies/${c.id}`);
          notifyOk('Компания удалена');
          navigate('/companies');
        } catch (e) {
          notifyError(e);
        }
      },
    });

  const openDeals = deals?.items.filter((d) => d.status === 'open') ?? [];

  return (
    <>
      <Anchor component={Link} to="/companies" size="sm" c="dimmed">
        <Group gap={4}>
          <IconArrowLeft size={14} /> Компании
        </Group>
      </Anchor>
      <Group justify="space-between" align="flex-start" mt="xs" mb="md" wrap="wrap">
        <div style={{ minWidth: 0, flex: 1 }}>
          <Group gap="sm">
            <Title order={2}>{c.name}</Title>
            <StatusBadge map={COMPANY_STATUS} value={c.status} size="md" />
          </Group>
          <Text c="dimmed" size="sm" mt={4}>
            {[c.inn && `ИНН ${c.inn}`, c.industry?.name, c.region?.name, c.client_type?.name].filter(Boolean).join(' · ')}
          </Text>
        </div>
        <Group gap="xs">
          <Button variant="default" leftSection={<IconMail size={16} />} onClick={() => setEmailTo(c.email)}>
            Письмо
          </Button>
          {can('deals.edit') && (
            <Button leftSection={<IconBriefcase size={16} />} onClick={() => setDealModal(true)}>
              Новая сделка
            </Button>
          )}
          {can('companies.edit') && (
            <Menu position="bottom-end">
              <Menu.Target>
                <Button variant="default" px="xs" aria-label="Ещё">
                  <IconDots size={18} />
                </Button>
              </Menu.Target>
              <Menu.Dropdown>
                <Menu.Item leftSection={<IconEdit size={16} />} onClick={() => setEdit(true)}>
                  Редактировать
                </Menu.Item>
                <Menu.Item leftSection={<IconUserPlus size={16} />} onClick={() => setContactModal({ open: true })}>
                  Добавить контакт
                </Menu.Item>
                {can('proposals.edit') && (
                  <Menu.Item leftSection={<IconFileText size={16} />}
                    onClick={async () => {
                      try {
                        const { data } = await api.post('/proposals', { company_id: c.id, template_id: 1 });
                        navigate(`/proposals/${data.id}`);
                      } catch (e) {
                        notifyError(e);
                      }
                    }}>
                    Создать КП
                  </Menu.Item>
                )}
                {can('companies.delete') && (
                  <>
                    <Menu.Divider />
                    <Menu.Item color="red" leftSection={<IconTrash size={16} />} onClick={remove}>
                      Удалить
                    </Menu.Item>
                  </>
                )}
              </Menu.Dropdown>
            </Menu>
          )}
        </Group>
      </Group>

      <SimpleGrid cols={{ base: 2, md: 4 }} mb="md">
        <Card padding="sm">
          <Text size="xs" c="dimmed">Сумма покупок</Text>
          <Text fw={700} size="lg">{money(c.total_revenue)}</Text>
        </Card>
        <Card padding="sm">
          <Text size="xs" c="dimmed">Сделок в работе</Text>
          <Text fw={700} size="lg">{c.open_deals}</Text>
        </Card>
        <Card padding="sm">
          <Text size="xs" c="dimmed">Последний контакт</Text>
          <Text fw={700} size="lg" c={!c.last_contact_at ? 'orange' : undefined}>{c.last_contact_at ? ago(c.last_contact_at) : 'не было'}</Text>
        </Card>
        <Card padding="sm">
          <Text size="xs" c="dimmed">Ответственный</Text>
          <Text fw={700} size="lg" truncate>{c.manager?.full_name ?? '—'}</Text>
        </Card>
      </SimpleGrid>

      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Card p={0}>
            <Tabs defaultValue="info" keepMounted={false}>
              <Tabs.List px="md" pt="xs">
                <Tabs.Tab value="info">Инфо</Tabs.Tab>
                <Tabs.Tab value="contacts" rightSection={<Badge size="xs" variant="light">{contacts?.total ?? 0}</Badge>}>
                  Контакты
                </Tabs.Tab>
                {can('deals.view') && (
                  <Tabs.Tab value="deals" rightSection={<Badge size="xs" variant="light">{deals?.total ?? 0}</Badge>}>
                    Сделки
                  </Tabs.Tab>
                )}
                {(can('proposals.edit') || can('finance.view')) && <Tabs.Tab value="docs">КП и счета</Tabs.Tab>}
                <Tabs.Tab value="files">Файлы</Tabs.Tab>
                <Tabs.Tab value="history">История</Tabs.Tab>
              </Tabs.List>

              <Tabs.Panel value="info" p="lg">
                <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }} spacing="md">
                  <Field label="Полное наименование">{c.full_name}</Field>
                  <Field label="ИНН / КПП">{[c.inn, c.kpp].filter(Boolean).join(' / ')}</Field>
                  <Field label="ОГРН">{c.ogrn}</Field>
                  <Field label="Телефон"><Phone phone={c.phone} links={{ company_id: c.id }} /></Field>
                  <Field label="Email">{c.email && <Anchor size="sm" onClick={() => setEmailTo(c.email)}>{c.email}</Anchor>}</Field>
                  <Field label="Сайт">{c.website && <Anchor size="sm" href={c.website.startsWith('http') ? c.website : `https://${c.website}`} target="_blank">{c.website}</Anchor>}</Field>
                  <Field label="Юридический адрес">{c.legal_address}</Field>
                  <Field label="Фактический адрес">{c.actual_address}</Field>
                  <Field label="Источник">{c.source?.name}</Field>
                  <Field label="Банк">{c.bank_name}</Field>
                  <Field label="БИК">{c.bik}</Field>
                  <Field label="Р/с">{c.account}</Field>
                  <CustomFieldsView entity="company" value={c.custom_fields} />
                  <Field label="В базе с">{date(c.created_at)}</Field>
                </SimpleGrid>
                {c.description && (
                  <Text size="sm" mt="md" style={{ whiteSpace: 'pre-wrap' }}>
                    {c.description}
                  </Text>
                )}
              </Tabs.Panel>

              <Tabs.Panel value="contacts" p="lg">
                <Group justify="flex-end" mb="sm">
                  {can('companies.edit') && (
                    <Button size="xs" leftSection={<IconPlus size={14} />} onClick={() => setContactModal({ open: true })}>
                      Контакт
                    </Button>
                  )}
                </Group>
                {!contacts?.items.length ? <Empty text="Контактов нет" /> : (
                  <Table.ScrollContainer minWidth={600}>
                    <Table>
                      <Table.Tbody>
                        {contacts.items.map((ct) => (
                          <Table.Tr key={ct.id}>
                            <Table.Td>
                              <EntityLink to={`/contacts/${ct.id}`}>{ct.full_name}</EntityLink>
                              <Text size="xs" c="dimmed">{ct.position}</Text>
                            </Table.Td>
                            <Table.Td>{ct.role_in_deal && <Badge size="sm" variant="outline">{CONTACT_ROLES[ct.role_in_deal]}</Badge>}</Table.Td>
                            <Table.Td><Phone phone={ct.phone_mobile || ct.phone_work} links={{ contact_id: ct.id }} /></Table.Td>
                            <Table.Td>{ct.email && <Anchor size="sm" onClick={() => setEmailTo(ct.email)}>{ct.email}</Anchor>}</Table.Td>
                            <Table.Td w={40}>
                              <Button size="compact-xs" variant="subtle" onClick={() => setContactModal({ open: true, contact: ct })}>
                                <IconEdit size={14} />
                              </Button>
                            </Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                )}
              </Tabs.Panel>

              <Tabs.Panel value="deals" p="lg">
                {!deals?.items.length ? <Empty text="Сделок нет" /> : (
                  <Table.ScrollContainer minWidth={600}>
                    <Table>
                      <Table.Thead>
                        <Table.Tr>
                          <Table.Th>Сделка</Table.Th><Table.Th>Этап</Table.Th><Table.Th ta="right">Сумма</Table.Th>
                          <Table.Th>Закрытие</Table.Th><Table.Th>Ответственный</Table.Th>
                        </Table.Tr>
                      </Table.Thead>
                      <Table.Tbody>
                        {deals.items.map((d) => (
                          <Table.Tr key={d.id} className="clickable-row" onClick={() => navigate(`/deals/${d.id}`)}>
                            <Table.Td>{d.title}</Table.Td>
                            <Table.Td>
                              {d.status === 'open' ? <Badge color={d.stage.color}>{d.stage.name}</Badge> : <StatusBadge map={DEAL_STATUS} value={d.status} />}
                            </Table.Td>
                            <Table.Td ta="right">{money(d.amount, d.currency)}</Table.Td>
                            <Table.Td>{date(d.closed_at ?? d.close_date)}</Table.Td>
                            <Table.Td>{d.owner?.full_name}</Table.Td>
                          </Table.Tr>
                        ))}
                      </Table.Tbody>
                    </Table>
                  </Table.ScrollContainer>
                )}
                {!!openDeals.length && (
                  <Text size="sm" c="dimmed" mt="sm">
                    В работе: {openDeals.length} на {money(openDeals.reduce((s, d) => s + d.amount, 0))}
                  </Text>
                )}
              </Tabs.Panel>

              <Tabs.Panel value="docs" p="lg">
                <Stack>
                  {can('proposals.edit') && (
                    <div>
                      <Title order={5} mb="xs">Коммерческие предложения</Title>
                      {!proposals?.items.length ? <Text size="sm" c="dimmed">Нет</Text> : (
                        <Table>
                          <Table.Tbody>
                            {proposals.items.map((p) => (
                              <Table.Tr key={p.id} className="clickable-row" onClick={() => navigate(`/proposals/${p.id}`)}>
                                <Table.Td>{p.number}</Table.Td>
                                <Table.Td>{p.title}</Table.Td>
                                <Table.Td ta="right">{money(p.total, p.currency)}</Table.Td>
                                <Table.Td><StatusBadge map={PROPOSAL_STATUS} value={p.status} /></Table.Td>
                              </Table.Tr>
                            ))}
                          </Table.Tbody>
                        </Table>
                      )}
                    </div>
                  )}
                  {can('finance.view') && (
                    <div>
                      <Title order={5} mb="xs">Счета</Title>
                      {!invoices?.items.length ? <Text size="sm" c="dimmed">Нет</Text> : (
                        <Table>
                          <Table.Tbody>
                            {invoices.items.map((i) => (
                              <Table.Tr key={i.id} className="clickable-row" onClick={() => navigate(`/finance?invoice=${i.id}`)}>
                                <Table.Td>{i.number}</Table.Td>
                                <Table.Td>{date(i.issued_at)}</Table.Td>
                                <Table.Td ta="right">{money(i.amount, i.currency)}</Table.Td>
                                <Table.Td>
                                  <StatusBadge map={INVOICE_STATUS} value={i.status} />
                                  {i.is_overdue && <Badge color="red" ml={4} size="sm">Просрочен</Badge>}
                                </Table.Td>
                              </Table.Tr>
                            ))}
                          </Table.Tbody>
                        </Table>
                      )}
                    </div>
                  )}
                </Stack>
              </Tabs.Panel>

              <Tabs.Panel value="files" p="lg">
                <FilesPanel companyId={c.id} />
              </Tabs.Panel>

              <Tabs.Panel value="history" p="lg">
                <Title order={5} mb="sm">Переписка</Title>
                <EmailHistory company_id={c.id} />
              </Tabs.Panel>
            </Tabs>
          </Card>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card>
              <Title order={5} mb="xs">Задачи</Title>
              <TasksPanel defaults={{ company_id: c.id }} />
            </Card>
            <Card>
              <Title order={5} mb="sm">Лента событий</Title>
              <Timeline filter={{ company_id: c.id }} />
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>

      <CompanyModal opened={edit} onClose={() => setEdit(false)} company={c} />
      <ContactModal opened={contactModal.open} onClose={() => setContactModal({ open: false })} contact={contactModal.contact}
        companyId={c.id} />
      <DealModal opened={dealModal} onClose={() => setDealModal(false)} defaults={{ company_id: c.id }}
        onSaved={(d) => navigate(`/deals/${d.id}`)} />
      <EmailModal opened={emailTo !== undefined} onClose={() => setEmailTo(undefined)} to={emailTo} links={{ company_id: c.id }} />
    </>
  );
}
