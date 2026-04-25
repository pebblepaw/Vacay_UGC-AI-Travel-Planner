import { Trip } from '@/data/mockData';

export function normalizeExternalAssetUrl(url?: string | null): string {
  if (!url) {
    return '';
  }

  if (url.startsWith('http://')) {
    return `https://${url.slice('http://'.length)}`;
  }

  return url;
}

export function normalizeTripAssetUrls(trip: Trip): Trip {
  return {
    ...trip,
    source_videos: trip.source_videos.map((video) => ({
      ...video,
      preview_url: normalizeExternalAssetUrl(video.preview_url),
      thumbnail_url: normalizeExternalAssetUrl(video.thumbnail_url),
    })),
    days: trip.days.map((day) => ({
      ...day,
      pois: day.pois.map((poi) => ({
        ...poi,
        img: normalizeExternalAssetUrl(poi.img),
      })),
    })),
    accommodation: {
      ...trip.accommodation,
      img: normalizeExternalAssetUrl(trip.accommodation.img),
    },
  };
}
