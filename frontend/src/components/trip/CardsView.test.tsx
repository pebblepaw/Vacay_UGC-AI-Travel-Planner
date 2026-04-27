import React from 'react';
import { fireEvent, render, screen } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const setSelectedPOI = vi.fn();

vi.mock('@/contexts/TripContext', () => ({
  useTripContext: () => ({
    trip: {
      trip_id: 'trip_test',
      title: 'Sydney Demo',
      source_videos: [],
      days: [
        {
          day_number: 1,
          date: '2026-05-01',
          pois: [
            {
              id: 'poi_coogee',
              name: 'Coogee Beach',
              category: 'Nature',
              coords: [151.255, -33.92],
              img: 'https://example.com/coogee.jpg',
              time_slot: '09:00 - 10:00',
              vibe: 'Coastal walk start.',
              travel_time: '10 min train',
            },
          ],
        },
      ],
      accommodation: {
        name: 'Demo Hotel',
        price_per_night: 200,
        status: 'Mock',
        img: 'https://example.com/hotel.jpg',
        coords: [151.2, -33.8],
      },
    },
    selectedPOI: null,
    setSelectedPOI,
    mediaByPlace: {
      poi_coogee: [
        {
          title: 'Coogee walk clip',
          url: 'https://cdn.example.com/coogee.mp4',
          platform: 'youtube',
          autoplay: true,
        },
        {
          title: 'Douyin source clip',
          url: 'https://v.douyin.com/demo',
          source_url: 'https://v.douyin.com/demo',
          platform: 'douyin',
          autoplay: false,
        },
      ],
    },
  }),
}));

vi.mock('framer-motion', async () => {
  const ReactModule = await import('react');

  const createMotionComponent = (tag: string) =>
    ReactModule.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement> & Record<string, unknown>>(
      ({ children, initial, animate, transition, whileHover, ...props }, ref) => {
        void initial;
        void animate;
        void transition;
        void whileHover;
        return ReactModule.createElement(tag, { ...props, ref } as React.HTMLAttributes<HTMLElement>, children);
      },
    );

  return {
    motion: new Proxy(
      {},
      {
        get: (_, tag: string) => createMotionComponent(tag),
      },
    ),
  };
});

import { CardsView } from './CardsView';

describe('CardsView', () => {
  beforeEach(() => {
    setSelectedPOI.mockClear();
  });

  it('opens a media overlay with autoplay video and source-link fallback', () => {
    render(<CardsView />);

    fireEvent.click(screen.getByRole('button', { name: /open media folder for coogee beach/i }));

    expect(screen.getByRole('dialog')).toBeInTheDocument();
    expect(screen.getAllByText('Coogee walk clip').length).toBeGreaterThan(0);
    expect(screen.getAllByText('Douyin source clip').length).toBeGreaterThan(0);
    const video = document.querySelector('video');
    expect(video).not.toBeNull();
    expect(video?.autoplay).toBe(true);

    fireEvent.click(screen.getByRole('button', { name: /douyin source clip douyin/i }));

    expect(screen.getByRole('link', { name: /open original douyin source/i })).toHaveAttribute(
      'href',
      'https://v.douyin.com/demo',
    );
  });
});
