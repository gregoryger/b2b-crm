import { useEffect, useState } from 'react';
import { Button, Group, Modal, MultiSelect, Stack, Text, Textarea, TextInput } from '@mantine/core';
import { useQueryClient } from '@tanstack/react-query';
import { api, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { FileItem } from '@/api/types';
import { useAuth } from '@/auth/AuthContext';

export default function EmailModal({ opened, onClose, to, links }: {
  opened: boolean; onClose: () => void; to?: string | null;
  links: { company_id?: number | null; contact_id?: number | null; deal_id?: number | null; lead_id?: number | null };
}) {
  const { user } = useAuth();
  const qc = useQueryClient();
  const [email, setEmail] = useState('');
  const [subject, setSubject] = useState('');
  const [body, setBody] = useState('');
  const [fileIds, setFileIds] = useState<string[]>([]);
  const [sending, setSending] = useState(false);
  const { data: files } = useApi<FileItem[]>(['files', links.deal_id, links.company_id],
    opened && (links.deal_id || links.company_id) ? '/files' : null,
    { deal_id: links.deal_id ?? undefined, company_id: links.deal_id ? undefined : links.company_id ?? undefined });

  useEffect(() => {
    if (opened) {
      setEmail(to ?? '');
      setSubject('');
      setBody(`Добрый день!\n\n\n\nС уважением,\n${user?.full_name ?? ''}\n${user?.position ?? ''}\n${user?.phone ?? ''}`);
      setFileIds([]);
    }
  }, [opened, to, user]);

  const send = async () => {
    setSending(true);
    try {
      await api.post('/emails', { to: email, subject, body, ...links, file_ids: fileIds.map(Number) });
      notifyOk('Письмо отправлено. Мы сообщим, когда его откроют.');
      qc.invalidateQueries({ queryKey: ['activities'] });
      onClose();
    } catch (e) {
      notifyError(e);
    } finally {
      setSending(false);
    }
  };

  return (
    <Modal opened={opened} onClose={onClose} title="Новое письмо" size="lg">
      <Stack>
        <TextInput label="Кому" value={email} onChange={(e) => setEmail(e.currentTarget.value)} />
        <TextInput label="Тема" value={subject} onChange={(e) => setSubject(e.currentTarget.value)} data-autofocus />
        <Textarea label="Текст" autosize minRows={8} value={body} onChange={(e) => setBody(e.currentTarget.value)} />
        {!!files?.length && (
          <MultiSelect label="Вложения" placeholder="Выберите файлы сделки" value={fileIds} onChange={setFileIds}
            data={files.map((f) => ({ value: String(f.id), label: f.name }))} clearable />
        )}
        <Text size="xs" c="dimmed">
          Письмо сохранится в ленте клиента; факт открытия отслеживается автоматически.
        </Text>
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>
            Отмена
          </Button>
          <Button onClick={send} loading={sending} disabled={!email || !subject || !body}>
            Отправить
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
