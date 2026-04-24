import { mapWorkspaceEventsToMessages } from './TripContext';

describe('TripContext workspace hydration', () => {
  it('maps snapshot recent_events into chat messages', () => {
    const result = mapWorkspaceEventsToMessages([
      {
        role: 'user',
        content: 'find flights',
        created_at: '2026-04-24T10:00:00Z',
      },
      {
        role: 'agent',
        content: 'I found 3 options',
        created_at: '2026-04-24T10:00:05Z',
      },
    ]);

    expect(result).toHaveLength(2);
    expect(result[0].type).toBe('user');
    expect(result[0].content).toBe('find flights');
    expect(result[1].type).toBe('agent');
    expect(result[1].content).toBe('I found 3 options');
  });
});
