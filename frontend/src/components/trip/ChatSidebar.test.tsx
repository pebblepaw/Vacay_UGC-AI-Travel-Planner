import React from 'react';
import { fireEvent, render, screen, waitFor } from '@testing-library/react';
import { beforeEach, describe, expect, it, vi } from 'vitest';

const sendUserMessage = vi.fn();
const setIsChatOpen = vi.fn();
const handleInterruptAction = vi.fn();
let mockChatMessages: any[] = [];

vi.mock('@/contexts/TripContext', () => ({
  useTripContext: () => ({
    isChatOpen: true,
    setIsChatOpen,
    chatMessages: mockChatMessages,
    sendUserMessage,
    handleInterruptAction,
  }),
}));

vi.mock('@/components/ui/sheet', () => ({
  Sheet: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetContent: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetHeader: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  SheetTitle: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
}));

vi.mock('@/components/ui/scroll-area', () => ({
  ScrollArea: React.forwardRef<HTMLDivElement, { children: React.ReactNode }>(({ children }, ref) => (
    <div ref={ref}>{children}</div>
  )),
}));

vi.mock('framer-motion', async () => {
  const ReactModule = await import('react');

  const createMotionComponent = (tag: string) =>
    ReactModule.forwardRef<HTMLElement, React.HTMLAttributes<HTMLElement>>(({ children, ...props }, ref) =>
      ReactModule.createElement(tag, { ...props, ref } as React.HTMLAttributes<HTMLElement>, children),
    );

  return {
    AnimatePresence: ({ children }: { children: React.ReactNode }) => <>{children}</>,
    motion: new Proxy(
      {},
      {
        get: (_, tag: string) => createMotionComponent(tag),
      },
    ),
  };
});

import { ChatSidebar } from './ChatSidebar';

describe('ChatSidebar', () => {
  beforeEach(() => {
    sendUserMessage.mockClear();
    setIsChatOpen.mockClear();
    handleInterruptAction.mockClear();
    mockChatMessages = [];
  });

  it('auto-grows the textarea up to a max height and clears after send', async () => {
    render(<ChatSidebar />);

    const textarea = screen.getByPlaceholderText('Ask anything about your trip...') as HTMLTextAreaElement;
    let nextScrollHeight = 220;

    Object.defineProperty(textarea, 'scrollHeight', {
      configurable: true,
      get: () => nextScrollHeight,
    });

    fireEvent.change(textarea, { target: { value: 'Line 1\nLine 2\nLine 3' } });

    await waitFor(() => {
      expect(textarea).toHaveStyle({ height: '160px' });
    });

    nextScrollHeight = 56;
    fireEvent.click(screen.getByRole('button', { name: /send message/i }));

    expect(sendUserMessage).toHaveBeenCalledWith('Line 1\nLine 2\nLine 3');

    await waitFor(() => {
      expect(textarea).toHaveValue('');
    });

    await waitFor(() => {
      expect(textarea).toHaveStyle({ height: '56px' });
    });
  });

  it('submits with Enter, preserves Shift+Enter, and keeps quick actions wired', () => {
    render(<ChatSidebar />);

    const textarea = screen.getByPlaceholderText('Ask anything about your trip...');

    fireEvent.change(textarea, { target: { value: 'Plan a day in Kyoto' } });
    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter', shiftKey: true });

    expect(sendUserMessage).not.toHaveBeenCalled();

    fireEvent.keyDown(textarea, { key: 'Enter', code: 'Enter' });

    expect(sendUserMessage).toHaveBeenCalledWith('Plan a day in Kyoto');

    fireEvent.click(screen.getByRole('button', { name: /cheaper hotel/i }));

    expect(sendUserMessage).toHaveBeenCalledWith('Can you find a cheaper hotel?');
  });

  it('keeps long chat bubbles constrained inside the sheet width classes', () => {
    mockChatMessages = [
      {
        id: 'agent_1',
        type: 'agent',
        content: 'VeryLongAirportCodeStringWithoutSpaces1234567890 and a markdown paragraph.',
        timestamp: new Date(),
      },
      {
        id: 'user_1',
        type: 'user',
        content: 'AnotherVeryLongAirportCodeStringWithoutSpaces1234567890',
        timestamp: new Date(),
      },
    ];

    const { container } = render(<ChatSidebar />);
    const classText = container.innerHTML;

    expect(classText).toContain('break-words');
    expect(classText).not.toContain('max-w-none');
  });

  it('renders open_url interrupts as clickable booking links instead of approval prompts', () => {
    mockChatMessages = [
      {
        id: 'interrupt_1',
        type: 'interrupt',
        interrupt_type: 'open_url',
        content: 'https://trip.com/flights/passenger?token=visible',
        status: 'pending',
        timestamp: new Date(),
      },
    ];

    render(<ChatSidebar />);

    expect(screen.getByRole('link', { name: /open booking handoff/i })).toHaveAttribute(
      'href',
      'https://trip.com/flights/passenger?token=visible',
    );
    expect(screen.queryByRole('button', { name: /approve/i })).not.toBeInTheDocument();
    expect(screen.queryByRole('button', { name: /reject/i })).not.toBeInTheDocument();
  });
});
