import { normalizeExternalAssetUrl, normalizeTripAssetUrls } from './assets';

describe('asset url normalization', () => {
  it('upgrades insecure external assets to https', () => {
    expect(normalizeExternalAssetUrl('http://example.com/photo.jpg')).toBe('https://example.com/photo.jpg');
  });

  it('normalizes trip-level image and preview urls', () => {
    const trip = normalizeTripAssetUrls({
      trip_id: 'trip_1',
      title: 'Demo',
      source_videos: [
        {
          platform: 'tiktok',
          url: 'https://tiktok.com/demo',
          title: 'Demo Clip',
          preview_url: 'http://example.com/video.mp4',
          thumbnail_url: 'http://example.com/thumb.jpg',
        },
      ],
      days: [
        {
          day_number: 1,
          date: '2026-05-01',
          pois: [
            {
              id: 'poi_1',
              name: 'Demo Place',
              category: 'Nature',
              coords: [0, 0],
              img: 'http://example.com/place.jpg',
              time_slot: '09:00 - 10:00',
              vibe: 'demo',
            },
          ],
        },
      ],
      accommodation: {
        name: 'Demo Stay',
        price_per_night: 100,
        status: 'Mock',
        img: 'http://example.com/stay.jpg',
        coords: [0, 0],
      },
    });

    expect(trip.source_videos[0].preview_url).toBe('https://example.com/video.mp4');
    expect(trip.source_videos[0].thumbnail_url).toBe('https://example.com/thumb.jpg');
    expect(trip.days[0].pois[0].img).toBe('https://example.com/place.jpg');
    expect(trip.accommodation.img).toBe('https://example.com/stay.jpg');
  });
});
