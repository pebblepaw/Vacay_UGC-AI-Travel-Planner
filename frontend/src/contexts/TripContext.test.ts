import { hydrateWorkspaceSnapshot, mapWorkspaceEventsToMessages } from './TripContext';

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

  it('hydrates trip, media folders, and chat from a workspace snapshot payload', () => {
    const result = hydrateWorkspaceSnapshot({
      workspace_id: 'telegram:-100:main',
      trip: { trip_id: 'trip_123', title: 'Sydney', days: [], source_videos: [], accommodation: {} },
      media_by_place: { poi_1: [{ title: 'Clip', url: 'https://example.com/clip.mp4', platform: 'instagram', autoplay: true }] },
      recent_events: [
        { role: 'user', content: 'Shrink it to 2 days', created_at: '2026-04-24T10:00:00Z' },
      ],
      runtime_state: {},
      workspace_memory: {},
      updated_at: '2026-04-24T10:00:01Z',
    });

    expect(result.trip.trip_id).toBe('trip_123');
    expect(result.mediaByPlace.poi_1).toHaveLength(1);
    expect(result.chatMessages).toHaveLength(1);
    expect(result.chatMessages[0].content).toBe('Shrink it to 2 days');
  });
});
