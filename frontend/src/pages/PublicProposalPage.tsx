import { useEffect, useState } from 'react';
import { useParams } from 'react-router-dom';
import axios from 'axios';
import { Alert, Box, Button, Card, Center, Container, Group, Image, Loader, Modal, Stack, Table, Text, Textarea, Title } from '@mantine/core';
import { IconCheck, IconDownload, IconX } from '@tabler/icons-react';
import { date, money } from '@/lib/format';

interface PublicProposal {
  number: string; title: string; status: string; currency: string; vat_rate: number; valid_until: string | null;
  created_at: string; intro: string; terms: string; total: number; vat: number;
  items: { n: number; name: string; description: string | null; quantity: number; unit: string; price: number; discount_percent: number; total: number }[];
  company: { name: string } | null;
  seller: { name: string; phone: string; email: string; website: string; has_logo: boolean; accent_color: string };
  manager: { name: string; phone: string | null; email: string; position: string | null } | null;
  client_comment: string | null; decided_at: string | null;
}

/** Публичная онлайн-версия КП для клиента: просмотр, скачивание PDF, согласование */
export default function PublicProposalPage() {
  const { token } = useParams();
  const [p, setP] = useState<PublicProposal | null>(null);
  const [error, setError] = useState(false);
  const [decision, setDecision] = useState<'approved' | 'rejected' | null>(null);
  const [comment, setComment] = useState('');
  const [sending, setSending] = useState(false);
  const load = () => axios.get(`/api/v1/public/proposals/${token}`).then((r) => setP(r.data)).catch(() => setError(true));
  useEffect(() => {
    load();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [token]);
  useEffect(() => {
    if (p) document.title = `${p.title} — ${p.seller.name}`;
  }, [p]);

  if (error) return <Center h="100vh"><Text c="dimmed">Предложение не найдено или ссылка устарела</Text></Center>;
  if (!p) return <Center h="100vh"><Loader /></Center>;
  const accent = p.seller.accent_color || '#1c7ed6';
  const decided = p.status === 'approved' || p.status === 'rejected';

  const submit = async () => {
    setSending(true);
    try {
      await axios.post(`/api/v1/public/proposals/${token}/decision`, { decision, comment: comment || null });
      setDecision(null);
      await load();
    } finally {
      setSending(false);
    }
  };

  return (
    <Box bg="gray.1" mih="100vh" py="xl">
      <Container size="md">
        <Card p={0} shadow="sm">
          <Box p="xl" style={{ borderBottom: `4px solid ${accent}` }}>
            <Group justify="space-between" align="flex-end">
              <div>
                {p.seller.has_logo ? <Image src="/api/v1/public/logo" h={44} w="auto" fit="contain" alt={p.seller.name} /> : <Title order={3}>{p.seller.name}</Title>}
                <Text size="xs" c="dimmed" mt={4}>{[p.seller.phone, p.seller.email, p.seller.website].filter(Boolean).join(' · ')}</Text>
              </div>
              <div style={{ textAlign: 'right' }}>
                <Title order={2} style={{ color: accent }}>Коммерческое предложение</Title>
                <Text size="sm" c="dimmed">№ {p.number} от {date(p.created_at)}</Text>
              </div>
            </Group>
          </Box>
          <Stack p="xl" gap="lg">
            {decided && (
              <Alert color={p.status === 'approved' ? 'teal' : 'gray'} icon={p.status === 'approved' ? <IconCheck /> : <IconX />}>
                {p.status === 'approved' ? 'Вы согласовали предложение. Менеджер свяжется с вами для оформления документов.' : 'Вы отклонили предложение.'}
                {p.client_comment && <> Ваш комментарий: «{p.client_comment}»</>}
              </Alert>
            )}
            <div>
              {p.company && <Text size="sm" c="dimmed">Для: <b>{p.company.name}</b></Text>}
              <Title order={3} mt={4}>{p.title}</Title>
              {p.valid_until && <Text size="sm" c="dimmed">Действует до {date(p.valid_until)}</Text>}
            </div>
            {p.intro && <Text style={{ whiteSpace: 'pre-line' }}>{p.intro}</Text>}
            <Table.ScrollContainer minWidth={560}>
              <Table striped>
                <Table.Thead style={{ background: accent }}>
                  <Table.Tr>
                    {['№', 'Наименование', 'Кол-во', 'Цена', 'Сумма'].map((h) => <Table.Th key={h} c="white">{h}</Table.Th>)}
                  </Table.Tr>
                </Table.Thead>
                <Table.Tbody>
                  {p.items.map((i) => (
                    <Table.Tr key={i.n}>
                      <Table.Td>{i.n}</Table.Td>
                      <Table.Td>{i.name}{i.description && <Text size="xs" c="dimmed">{i.description}</Text>}</Table.Td>
                      <Table.Td>{i.quantity} {i.unit}</Table.Td>
                      <Table.Td>{money(i.price, p.currency, 2)}{i.discount_percent > 0 && <Text size="xs" c="teal">−{i.discount_percent}%</Text>}</Table.Td>
                      <Table.Td fw={500}>{money(i.total, p.currency, 2)}</Table.Td>
                    </Table.Tr>
                  ))}
                </Table.Tbody>
              </Table>
            </Table.ScrollContainer>
            <Group justify="flex-end">
              <div style={{ textAlign: 'right' }}>
                <Text fz={26} fw={800} style={{ color: accent }}>{money(p.total, p.currency, 2)}</Text>
                <Text size="sm" c="dimmed">{p.vat_rate ? `в т.ч. НДС ${p.vat_rate}%: ${money(p.vat, p.currency, 2)}` : 'НДС не облагается'}</Text>
              </div>
            </Group>
            {p.terms && (
              <div>
                <Title order={4} mb="xs">Условия</Title>
                <Text size="sm" style={{ whiteSpace: 'pre-line' }}>{p.terms}</Text>
              </div>
            )}
            {p.manager && (
              <Card withBorder bg="gray.0" style={{ borderLeft: `4px solid ${accent}` }}>
                <Text size="sm"><b>Ваш менеджер:</b> {p.manager.name}{p.manager.position && `, ${p.manager.position}`}</Text>
                <Text size="sm" c="dimmed">{[p.manager.phone, p.manager.email].filter(Boolean).join(' · ')}</Text>
              </Card>
            )}
            <Group justify="space-between" className="no-print">
              <Button variant="default" leftSection={<IconDownload size={16} />} component="a" href={`/api/v1/public/proposals/${token}/pdf`} target="_blank">
                Скачать PDF
              </Button>
              {!decided && (
                <Group>
                  <Button variant="default" color="red" onClick={() => setDecision('rejected')}>Отклонить</Button>
                  <Button color="teal" leftSection={<IconCheck size={16} />} onClick={() => setDecision('approved')} style={{ background: accent }}>
                    Согласовать предложение
                  </Button>
                </Group>
              )}
            </Group>
          </Stack>
        </Card>
      </Container>
      <Modal opened={!!decision} onClose={() => setDecision(null)} title={decision === 'approved' ? 'Согласовать предложение' : 'Отклонить предложение'}>
        <Stack>
          <Textarea label={decision === 'approved' ? 'Комментарий (необязательно)' : 'Подскажите, что не подошло? (необязательно)'}
            autosize minRows={3} value={comment} onChange={(e) => setComment(e.currentTarget.value)} />
          <Group justify="flex-end">
            <Button variant="default" onClick={() => setDecision(null)}>Отмена</Button>
            <Button color={decision === 'approved' ? 'teal' : 'red'} loading={sending} onClick={submit}>Подтвердить</Button>
          </Group>
        </Stack>
      </Modal>
    </Box>
  );
}
