import { useState } from 'react';
import { Button, Group, Modal, Stack, Textarea } from '@mantine/core';
import { DictSelect } from '@/components/selects';

/** Причина проигрыша обязательна — нужна для аналитики отказов */
export default function LostModal({ opened, onClose, onConfirm }: {
  opened: boolean; onClose: () => void; onConfirm: (reasonId: number, comment: string) => void;
}) {
  const [reason, setReason] = useState<number | null>(null);
  const [comment, setComment] = useState('');
  return (
    <Modal opened={opened} onClose={onClose} title="Сделка проиграна">
      <Stack>
        <DictSelect kind="loss_reason" label="Причина" withAsterisk value={reason} onChange={setReason} data-autofocus />
        <Textarea label="Комментарий" autosize minRows={2} value={comment} onChange={(e) => setComment(e.currentTarget.value)} />
        <Group justify="flex-end">
          <Button variant="default" onClick={onClose}>Отмена</Button>
          <Button color="red" disabled={!reason} onClick={() => {
            onConfirm(reason!, comment);
            setReason(null);
            setComment('');
          }}>
            Подтвердить
          </Button>
        </Group>
      </Stack>
    </Modal>
  );
}
