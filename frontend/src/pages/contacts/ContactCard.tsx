import { useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import { Anchor, Badge, Button, Card, Center, Grid, Group, Loader, SimpleGrid, Stack, Text, Title } from '@mantine/core';
import { modals } from '@mantine/modals';
import { IconArrowLeft, IconBrandTelegram, IconBrandWhatsapp, IconEdit, IconMail, IconTrash } from '@tabler/icons-react';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { Contact } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';
import { CustomFieldsView } from '@/components/CustomFields';
import EmailHistory from '@/components/EmailHistory';
import EmailModal from '@/components/EmailModal';
import { ContactModal } from '@/components/forms';
import TasksPanel from '@/components/TasksPanel';
import Timeline from '@/components/Timeline';
import { Empty, EntityLink, Field, Phone } from '@/components/ui';
import { date } from '@/lib/format';
import { CONTACT_ROLES } from '@/lib/labels';

export default function ContactCard() {
  const { id } = useParams();
  const navigate = useNavigate();
  const { can } = useAuth();
  const [edit, setEdit] = useState(false);
  const [email, setEmail] = useState(false);
  const { data: c, isLoading } = useApi<Contact>(['contact', Number(id)], `/contacts/${id}`);
  if (isLoading) return <Center h="50vh"><Loader /></Center>;
  if (!c) return <Empty text="Контакт не найден или нет доступа" />;

  const remove = () =>
    modals.openConfirmModal({
      title: 'Удалить контакт?',
      children: <Text size="sm">{c.full_name} будет удалён из базы.</Text>,
      labels: { confirm: 'Удалить', cancel: 'Отмена' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        try {
          await api.delete(`/contacts/${c.id}`);
          notifyOk('Контакт удалён');
          navigate('/contacts');
        } catch (e) {
          notifyError(e);
        }
      },
    });

  const links = { contact_id: c.id, company_id: c.company?.id };
  return (
    <>
      <Anchor component={Link} to="/contacts" size="sm" c="dimmed">
        <Group gap={4}><IconArrowLeft size={14} /> Контакты</Group>
      </Anchor>
      <Group justify="space-between" mt="xs" mb="md" align="flex-start">
        <div>
          <Group gap="sm">
            <Title order={2}>{c.full_name}</Title>
            {c.role_in_deal && <Badge size="lg" variant="outline">{CONTACT_ROLES[c.role_in_deal]}</Badge>}
          </Group>
          <Text c="dimmed" size="sm" mt={4}>
            {c.position}
            {c.company && <> · <EntityLink to={`/companies/${c.company.id}`}>{c.company.name}</EntityLink></>}
          </Text>
        </div>
        <Group gap="xs">
          {c.email && <Button variant="default" leftSection={<IconMail size={16} />} onClick={() => setEmail(true)}>Письмо</Button>}
          {can('companies.edit') && <Button variant="default" leftSection={<IconEdit size={16} />} onClick={() => setEdit(true)}>Изменить</Button>}
          {can('companies.edit') && <Button variant="subtle" color="red" onClick={remove} aria-label="Удалить"><IconTrash size={16} /></Button>}
        </Group>
      </Group>
      <Grid>
        <Grid.Col span={{ base: 12, lg: 8 }}>
          <Stack>
            <Card>
              <SimpleGrid cols={{ base: 1, sm: 2, md: 3 }}>
                <Field label="Мобильный"><Phone phone={c.phone_mobile} links={links} /></Field>
                <Field label="Рабочий"><Phone phone={c.phone_work} links={links} /></Field>
                <Field label="Email">{c.email && <Anchor size="sm" onClick={() => setEmail(true)}>{c.email}</Anchor>}</Field>
                <Field label="Telegram">
                  {c.telegram && (
                    <Anchor size="sm" href={`https://t.me/${c.telegram.replace('@', '')}`} target="_blank">
                      <Group gap={4}><IconBrandTelegram size={14} />{c.telegram}</Group>
                    </Anchor>
                  )}
                </Field>
                <Field label="WhatsApp">
                  {c.whatsapp && (
                    <Anchor size="sm" href={`https://wa.me/${c.whatsapp.replace(/\D/g, '')}`} target="_blank">
                      <Group gap={4}><IconBrandWhatsapp size={14} />{c.whatsapp}</Group>
                    </Anchor>
                  )}
                </Field>
                <Field label="Ответственный">{c.owner?.full_name}</Field>
                <CustomFieldsView entity="contact" value={c.custom_fields} />
                <Field label="Добавлен">{date(c.created_at)}</Field>
              </SimpleGrid>
              {c.notes && <Text size="sm" mt="md" style={{ whiteSpace: 'pre-wrap' }}>{c.notes}</Text>}
            </Card>
            <Card>
              <Title order={5} mb="sm">Переписка</Title>
              <EmailHistory contact_id={c.id} />
            </Card>
          </Stack>
        </Grid.Col>
        <Grid.Col span={{ base: 12, lg: 4 }}>
          <Stack>
            <Card>
              <Title order={5} mb="xs">Задачи</Title>
              <TasksPanel defaults={{ contact_id: c.id, company_id: c.company?.id }} />
            </Card>
            <Card>
              <Title order={5} mb="sm">Лента событий</Title>
              <Timeline filter={{ contact_id: c.id }} />
            </Card>
          </Stack>
        </Grid.Col>
      </Grid>
      <ContactModal opened={edit} onClose={() => setEdit(false)} contact={c} />
      <EmailModal opened={email} onClose={() => setEmail(false)} to={c.email} links={links} />
    </>
  );
}
