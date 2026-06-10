import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { vi } from 'vitest';

import { AddUrlModal, parseUrlsInput } from './AddUrlModal';

const ingestWorkspaceUrls = vi.fn();
const refreshWorkspaceSnapshot = vi.fn();

vi.mock('@/contexts/TripContext', () => ({
  useTripContext: () => ({
    workspaceId: 'telegram:-100:main',
    ingestWorkspaceUrls,
    refreshWorkspaceSnapshot,
  }),
}));

vi.mock('@/hooks/use-toast', () => ({
  useToast: () => ({ toast: vi.fn() }),
}));

vi.mock('@/lib/api', () => ({
  processVideos: vi.fn(),
}));

describe('AddUrlModal', () => {
  beforeEach(() => {
    ingestWorkspaceUrls.mockReset();
    refreshWorkspaceSnapshot.mockReset();
    ingestWorkspaceUrls.mockResolvedValue({ imported: 2, failed: 0 });
    refreshWorkspaceSnapshot.mockResolvedValue(undefined);
  });

  it('parses multi-link input with dedupe', () => {
    const urls = parseUrlsInput(`https://a.com/1\nhttps://b.com/2, https://a.com/1`);
    expect(urls).toEqual(['https://a.com/1', 'https://b.com/2']);
  });

  it('submits parsed links to workspace ingest flow', async () => {
    render(<AddUrlModal />);

    fireEvent.click(screen.getByRole('button'));

    const textarea = await screen.findByPlaceholderText(/Paste one or more links/i);
    fireEvent.change(textarea, {
      target: {
        value: 'https://youtube.com/watch?v=1\nhttps://instagram.com/reel/2\nhttps://youtube.com/watch?v=1',
      },
    });

    fireEvent.click(screen.getByRole('button', { name: /Add 2 Links/i }));

    await waitFor(() => {
      expect(ingestWorkspaceUrls).toHaveBeenCalledWith([
        'https://youtube.com/watch?v=1',
        'https://instagram.com/reel/2',
      ]);
      expect(refreshWorkspaceSnapshot).toHaveBeenCalled();
    });
  });

  it('renders a dialog description for assistive technologies', async () => {
    render(<AddUrlModal />);

    fireEvent.click(screen.getByRole('button'));

    expect(
      await screen.findByText(/Paste travel video links from TikTok, YouTube, Instagram, Douyin, or Rednote/i),
    ).toBeInTheDocument();
  });

  it('treats xhslink short links as Rednote in the modal', async () => {
    render(<AddUrlModal />);

    fireEvent.click(screen.getByRole('button'));

    const textarea = await screen.findByPlaceholderText(/Paste one or more links/i);
    fireEvent.change(textarea, {
      target: {
        value: 'https://xhslink.com/a/demo123',
      },
    });

    expect(screen.getByText('1 link(s) detected')).toBeInTheDocument();
    const rednoteBadge = screen.getAllByText(/Rednote/).at(-1);
    expect(rednoteBadge).toHaveClass('ring-2');
  });
});
