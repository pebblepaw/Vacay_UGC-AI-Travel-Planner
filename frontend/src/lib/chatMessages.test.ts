import { describe, expect, it } from 'vitest';

import { createClientMessageId } from './chatMessages';


describe('createClientMessageId', () => {
  it('returns unique ids across rapid successive calls', () => {
    const ids = Array.from({ length: 100 }, () => createClientMessageId());

    expect(new Set(ids).size).toBe(ids.length);
  });
});
