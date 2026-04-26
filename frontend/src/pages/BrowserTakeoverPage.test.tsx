import { render, screen, waitFor } from '@testing-library/react';
import { MemoryRouter, Route, Routes } from 'react-router-dom';
import { vi } from 'vitest';

import { getBrowserTakeoverSession } from '@/lib/api';
import BrowserTakeoverPage from './BrowserTakeoverPage';

vi.mock('@/lib/api', async () => {
  const actual = await vi.importActual<typeof import('@/lib/api')>('@/lib/api');
  return {
    ...actual,
    getBrowserTakeoverSession: vi.fn(),
  };
});

describe('BrowserTakeoverPage', () => {
  it('loads the signed takeover session and renders the remote browser iframe', async () => {
    vi.mocked(getBrowserTakeoverSession).mockResolvedValue({
      session_id: 'trip_session_demo',
      workspace_id: 'telegram:-100:main',
      active: true,
      current_url: 'https://www.trip.com/flights/passenger?booking=123',
      embed_url: 'https://demo.vacay.ai/remote-browser/vnc.html',
    });

    render(
      <MemoryRouter initialEntries={['/browser?token=signed-browser-token']}>
        <Routes>
          <Route path="/browser" element={<BrowserTakeoverPage />} />
        </Routes>
      </MemoryRouter>,
    );

    const frame = await screen.findByTitle(/vacayclaw remote browser/i);
    expect(frame).toHaveAttribute('src', 'https://demo.vacay.ai/remote-browser/vnc.html');
    expect(screen.getByText(/traveler page/i)).toBeInTheDocument();
  });
});
