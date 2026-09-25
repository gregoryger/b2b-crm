import { useState } from 'react';
import {
  Alert,
  Anchor,
  Button,
  Group,
  List,
  Modal,
  Radio,
  ScrollArea,
  Select,
  Stack,
  Table,
  Text,
} from '@mantine/core';
import { Dropzone } from '@mantine/dropzone';
import { IconCheck, IconFileSpreadsheet } from '@tabler/icons-react';
import { useQueryClient } from '@tanstack/react-query';
import { api, download, notifyError } from '@/api/client';

interface Preview {
  headers: string[];
  mapping: Record<string, string>;
  fields: Record<string, string>;
  total: number;
  sample: Record<string, string>[];
}

export default function ImportModal({ opened, onClose }: { opened: boolean; onClose: () => void }) {
  const qc = useQueryClient();
  const [file, setFile] = useState<File | null>(null);
  const [preview, setPreview] = useState<Preview | null>(null);
  const [mapping, setMapping] = useState<Record<string, string>>({});
  const [dup, setDup] = useState('skip');
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<{ created: number; updated: number; skipped: number; contacts: number;
    errors: { row: number; error: string }[] } | null>(null);

  const reset = () => {
    setFile(null);
    setPreview(null);
    setResult(null);
    setMapping({});
  };

  const load = async (f: File) => {
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', f);
      const { data } = await api.post<Preview>('/import/companies/preview', fd);
      setFile(f);
      setPreview(data);
      setMapping(data.mapping);
    } catch (e) {
      notifyError(e, 'Не удалось прочитать файл');
    } finally {
      setLoading(false);
    }
  };

  const run = async () => {
    if (!file) return;
    setLoading(true);
    try {
      const fd = new FormData();
      fd.append('file', file);
      fd.append('mapping', JSON.stringify(mapping));
      fd.append('on_duplicate', dup);
      const { data } = await api.post('/import/companies', fd);
      setResult(data);
      qc.invalidateQueries({ queryKey: ['companies'] });
    } catch (e) {
      notifyError(e, 'Ошибка импорта');
    } finally {
      setLoading(false);
    }
  };

  const fieldOptions = preview
    ? [{ value: '', label: '— не загружать —' }, ...Object.entries(preview.fields).map(([value, label]) => ({ value, label }))]
    : [];

  return (
    <Modal opened={opened} onClose={() => { reset(); onClose(); }} title="Импорт компаний и контактов" size="xl">
      {result ? (
        <Stack>
          <Alert color="teal" icon={<IconCheck />} title="Импорт завершён">
            Создано компаний: <b>{result.created}</b>, обновлено: <b>{result.updated}</b>, пропущено: <b>{result.skipped}</b>,
            добавлено контактов: <b>{result.contacts}</b>
          </Alert>
          {!!result.errors.length && (
            <Alert color="orange" title="Предупреждения">
              <List size="sm">
                {result.errors.slice(0, 20).map((e) => (
                  <List.Item key={e.row}>
                    Строка {e.row}: {e.error}
                  </List.Item>
                ))}
              </List>
            </Alert>
          )}
          <Group justify="flex-end">
            <Button onClick={() => { reset(); onClose(); }}>Готово</Button>
          </Group>
        </Stack>
      ) : !preview ? (
        <Stack>
          <Text size="sm">
            Загрузите файл CSV или Excel (.xlsx). Первая строка — заголовки колонок. Дубли определяются по ИНН.
          </Text>
          <Anchor size="sm" onClick={() => download('/import/template', undefined, 'import_template.xlsx')}>
            Скачать шаблон файла
          </Anchor>
          <Dropzone onDrop={(f) => f[0] && load(f[0])} loading={loading} multiple={false}
            accept={['text/csv', 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
              'application/vnd.ms-excel', 'text/plain']}>
            <Group justify="center" mih={120} style={{ pointerEvents: 'none' }}>
              <IconFileSpreadsheet size={40} color="var(--mantine-color-dimmed)" />
              <Text c="dimmed">Перетащите файл или нажмите для выбора</Text>
            </Group>
          </Dropzone>
        </Stack>
      ) : (
        <Stack>
          <Text size="sm">
            Файл <b>{file?.name}</b>: {preview.total} строк. Сопоставьте колонки файла с полями CRM:
          </Text>
          <ScrollArea h={300}>
            <Table>
              <Table.Thead>
                <Table.Tr>
                  <Table.Th>Колонка в файле</Table.Th>
                  <Table.Th>Пример</Table.Th>
                  <Table.Th w={260}>Поле в CRM</Table.Th>
                </Table.Tr>
              </Table.Thead>
              <Table.Tbody>
                {preview.headers.map((h) => (
                  <Table.Tr key={h}>
                    <Table.Td fw={500}>{h}</Table.Td>
                    <Table.Td c="dimmed">
                      <Text size="sm" truncate maw={220}>
                        {preview.sample[0]?.[h]}
                      </Text>
                    </Table.Td>
                    <Table.Td>
                      <Select size="xs" data={fieldOptions} value={mapping[h] ?? ''} allowDeselect={false}
                        onChange={(v) => setMapping({ ...mapping, [h]: v || '' })} aria-label={`Поле для ${h}`} />
                    </Table.Td>
                  </Table.Tr>
                ))}
              </Table.Tbody>
            </Table>
          </ScrollArea>
          <Radio.Group label="Если компания с таким ИНН уже есть" value={dup} onChange={setDup}>
            <Group mt="xs">
              <Radio value="skip" label="Пропустить" />
              <Radio value="update" label="Обновить данные" />
            </Group>
          </Radio.Group>
          <Group justify="space-between">
            <Button variant="default" onClick={reset}>
              Другой файл
            </Button>
            <Button onClick={run} loading={loading} disabled={!Object.values(mapping).includes('name')}>
              Импортировать {preview.total} строк
            </Button>
          </Group>
        </Stack>
      )}
    </Modal>
  );
}
