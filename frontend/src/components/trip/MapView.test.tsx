import React from 'react';
import { render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

vi.mock('mapbox-gl', () => ({
  default: {
    Map: vi.fn(),
    NavigationControl: vi.fn(),
    Marker: vi.fn(),
    Popup: vi.fn(),
    LngLatBounds: vi.fn(() => ({
      extend: vi.fn(),
    })),
  },
}));

const setSelectedPOI = vi.fn();

vi.mock('@/contexts/TripContext', () => ({
  useTripContext: () => ({
    trip: {
      title: 'Shanghai Import',
      days: [
        {
          day_number: 1,
          date: '2026-04-20',
          pois: [
            {
              id: 'poi_1',
              name: 'Wukang Building',
              category: 'Culture',
              coords: [121.43746, 31.20518],
              img: 'https://example.com/1.jpg',
              time_slot: '10:00 - 11:30',
              vibe: 'Historic icon',
            },
          ],
        },
      ],
    },
    selectedPOI: null,
    setSelectedPOI,
  }),
}));

import { MapView } from './MapView';

describe('MapView', () => {
  beforeEach(() => {
    vi.unstubAllEnvs();
  });

  it('shows a visible configuration error when the frontend Mapbox token is missing', () => {
    vi.stubEnv('VITE_MAPBOX_PUBLIC', '');

    render(<MapView />);

    expect(screen.getAllByText(/Mapbox token missing/i).length).toBeGreaterThan(0);
    expect(screen.getByText(/set MAPBOX_PUBLIC/i)).toBeInTheDocument();
  });
});
