import type { ChatMessage } from '@/data/mockData';

export type PendingChatMessage = Omit<ChatMessage, 'id' | 'timestamp'> & {
  id?: string;
  timestamp?: Date;
};


export const createClientMessageId = (prefix = 'msg'): string => {
  if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
    return `${prefix}_${crypto.randomUUID()}`;
  }

  return `${prefix}_${Date.now()}_${Math.random().toString(36).slice(2, 8)}`;
};
