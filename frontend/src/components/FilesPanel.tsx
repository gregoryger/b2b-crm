import { useState } from 'react';
import { ActionIcon, Badge, Group, Select, Stack, Table, Text, Tooltip } from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconDownload, IconTrash, IconUpload } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { modals } from '@mantine/modals';
import { api, download, notifyError, notifyOk } from '@/api/client';
import { useApi } from '@/api/hooks';
import type { FileItem } from '@/api/types';
import { date, fileSize } from '@/lib/format';
import { DOC_TYPES } from '@/lib/labels';

export default function FilesPanel({ dealId, companyId }: { dealId?: number; companyId?: number }) {
  const qc = useQueryClient();
  const [docType, setDocType] = useState('other');
  const [uploading, setUploading] = useState(false);
  const { data } = useApi<FileItem[]>(['files', dealId, companyId], '/files', { deal_id: dealId, company_id: companyId });

  const upload = async (files: File[]) => {
    setUploading(true);
    try {
      for (const f of files) {
        const fd = new FormData();
        fd.append('file', f);
        fd.append('doc_type', docType);
        if (dealId) fd.append('deal_id', String(dealId));
        if (companyId && !dealId) fd.append('company_id', String(companyId));
        await api.post('/files', fd);
      }
      notifyOk(files.length > 1 ? `Загружено файлов: ${files.length}` : 'Файл загружен');
      qc.invalidateQueries({ queryKey: ['files'] });
      qc.invalidateQueries({ queryKey: ['activities'] });
    } catch (e) {
      notifyError(e, 'Ошибка загрузки');
    } finally {
      setUploading(false);
    }
  };

  const remove = (f: FileItem) =>
    modals.openConfirmModal({
      title: 'Удалить файл?',
      children: <Text size="sm">«{f.name}» будет удалён без возможности восстановления.</Text>,
      labels: { confirm: 'Удалить', cancel: 'Отмена' },
      confirmProps: { color: 'red' },
      onConfirm: async () => {
        await api.delete(`/files/${f.id}`).catch(notifyError);
        qc.invalidateQueries({ queryKey: ['files'] });
      },
    });

  return (
    <Stack>
      <Group align="flex-end">
        <Select label="Тип документа" size="xs" w={180} value={docType} onChange={(v) => setDocType(v || 'other')}
          data={Object.entries(DOC_TYPES).map(([value, label]) => ({ value, label }))} allowDeselect={false} />
      </Group>
      <Dropzone onDrop={upload} loading={uploading} maxSize={25 * 1024 * 1024}
        onReject={() => notifyError({ message: '' }, 'Файл больше 25 МБ')}>
        <Group justify="center" gap="sm" mih={60} style={{ pointerEvents: 'none' }}>
          <IconUpload size={22} color="var(--mantine-color-dimmed)" />
          <Text size="sm" c="dimmed">
            Перетащите файлы сюда или нажмите для выбора (до 25 МБ)
          </Text>
        </Group>
      </Dropzone>
      {!!data?.length && (
        <Table>
          <Table.Tbody>
            {data.map((f) => (
              <Table.Tr key={f.id}>
                <Table.Td>
                  <Text size="sm" fw={500} style={{ wordBreak: 'break-all' }}>
                    {f.name}
                  </Text>
                  <Text size="xs" c="dimmed">
                    {date(f.created_at)} · {f.uploader?.full_name ?? '—'} · {fileSize(f.size)}
                  </Text>
                </Table.Td>
                <Table.Td w={110}>
                  <Badge size="sm" variant="outline">
                    {DOC_TYPES[f.doc_type] ?? f.doc_type}
                  </Badge>
                </Table.Td>
                <Table.Td w={80}>
                  <Group gap={4} wrap="nowrap">
                    <Tooltip label="Скачать">
                      <ActionIcon variant="subtle" onClick={() => download(`/files/${f.id}/download`, undefined, f.name)}
                        aria-label="Скачать">
                        <IconDownload size={16} />
                      </ActionIcon>
                    </Tooltip>
                    <Tooltip label="Удалить">
                      <ActionIcon variant="subtle" color="red" onClick={() => remove(f)} aria-label="Удалить">
                        <IconTrash size={16} />
                      </ActionIcon>
                    </Tooltip>
                  </Group>
                </Table.Td>
              </Table.Tr>
            ))}
          </Table.Tbody>
        </Table>
      )}
    </Stack>
  );
}
