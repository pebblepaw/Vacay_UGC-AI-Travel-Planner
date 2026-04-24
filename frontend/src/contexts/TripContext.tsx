import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react';
import { Trip, POI, ChatMessage, sampleTrip, initialChatMessages } from '@/data/mockData';
import {
  getTrip,
  sendChatMessage,
  listTrips,
  sendWorkspaceMessage,
  getWorkspaceSnapshot,
  createWorkspaceShareLink,
  processWorkspaceVideos,
} from '@/lib/api';
import { createClientMessageId, PendingChatMessage } from '@/lib/chatMessages';
import { useToast } from '@/hooks/use-toast';

interface TripContextType {
  trip: Trip;
  workspaceId?: string;
  workspaceToken?: string;
  selectedPOI: POI | null;
  setSelectedPOI: (poi: POI | null) => void;
  chatMessages: ChatMessage[];
  addChatMessage: (message: PendingChatMessage) => void;
  sendUserMessage: (content: string) => void;
  handleInterruptAction: (messageId: string, action: 'approve' | 'reject', optionId?: string) => void;
  isChatOpen: boolean;
  setIsChatOpen: (open: boolean) => void;
  activeView: 'timeline' | 'cards';
  setActiveView: (view: 'timeline' | 'cards') => void;
  isLoading: boolean;
  mediaByPlace: Record<string, Array<{ title: string; url: string; platform: string; autoplay: boolean }>>;
  createShareLink: () => Promise<string | null>;
  refreshWorkspaceSnapshot: () => Promise<void>;
  ingestWorkspaceUrls: (urls: string[]) => Promise<{ imported: number; failed: number }>;
}

const TripContext = createContext<TripContextType | undefined>(undefined);

export const useTripContext = () => {
  const context = useContext(TripContext);
  if (!context) {
    throw new Error('useTripContext must be used within a TripProvider');
  }
  return context;
};

interface TripProviderProps {
  children: ReactNode;
  tripId?: string;
  workspaceId?: string;
  workspaceToken?: string;
}

export const mapWorkspaceEventsToMessages = (events: Array<Record<string, unknown>>): ChatMessage[] => {
  return events
    .filter((event) => typeof event.content === 'string' && typeof event.role === 'string')
    .map((event, index) => ({
      id: createClientMessageId(`ev_${index}`),
      type: event.role === 'user' ? 'user' : 'agent',
      content: String(event.content),
      timestamp: new Date(String(event.created_at || new Date().toISOString())),
    }));
};

export const TripProvider: React.FC<TripProviderProps> = ({ children, tripId, workspaceId, workspaceToken }) => {
  const [trip, setTrip] = useState<Trip>(sampleTrip);
  const [selectedPOI, setSelectedPOI] = useState<POI | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(workspaceId ? [] : initialChatMessages);
  const [mediaByPlace, setMediaByPlace] = useState<Record<string, Array<{ title: string; url: string; platform: string; autoplay: boolean }>>>({});
  const chatMessagesRef = useRef<ChatMessage[]>(workspaceId ? [] : initialChatMessages);

  useEffect(() => {
    chatMessagesRef.current = chatMessages;
  }, [chatMessages]);

  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeView, setActiveView] = useState<'timeline' | 'cards'>('timeline');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  const refreshWorkspaceSnapshot = useCallback(async () => {
    if (!workspaceId) return;
    const snapshot = await getWorkspaceSnapshot(workspaceId, workspaceToken);
    setTrip(snapshot.trip);
    setMediaByPlace(snapshot.media_by_place || {});
    setChatMessages(mapWorkspaceEventsToMessages(snapshot.recent_events || []));
  }, [workspaceId, workspaceToken]);

  useEffect(() => {
    const loadTrip = async (id: string) => {
      setIsLoading(true);
      try {
        const data = await getTrip(id);
        setTrip(data);
        setChatMessages([
          {
            id: createClientMessageId(),
            type: 'agent',
            content: `Hey! 👋 I've loaded your trip "${data.title}". Feel free to ask me anything!`,
            timestamp: new Date(),
          },
        ]);
      } catch (error: any) {
        toast({ variant: 'destructive', title: 'Error loading trip', description: error.message });
      } finally {
        setIsLoading(false);
      }
    };

    const loadWorkspaceSnapshot = async () => {
      if (!workspaceId) return;
      setIsLoading(true);
      try {
        await refreshWorkspaceSnapshot();
      } catch (error: any) {
        toast({ variant: 'destructive', title: 'Workspace load failed', description: error.message });
      } finally {
        setIsLoading(false);
      }
    };

    if (workspaceId) {
      loadWorkspaceSnapshot();
      const timer = setInterval(loadWorkspaceSnapshot, 6000);
      return () => clearInterval(timer);
    }

    if (tripId) {
      loadTrip(tripId);
      return;
    }

    setIsLoading(true);
    listTrips()
      .then((data) => {
        if (data.trips && data.trips.length > 0) {
          const latest = data.trips[0];
          setTrip(latest);
          setChatMessages([
            {
              id: createClientMessageId(),
              type: 'agent',
              content: `Hey! 👋 I've loaded your trip "${latest.title}". Feel free to ask me anything!`,
              timestamp: new Date(),
            },
          ]);
        }
      })
      .catch(() => {
        // fallback to sample data
      })
      .finally(() => setIsLoading(false));
  }, [tripId, workspaceId, workspaceToken, toast, refreshWorkspaceSnapshot]);

  const addChatMessage = useCallback((message: PendingChatMessage) => {
    const newMessage: ChatMessage = {
      ...message,
      id: message.id ?? createClientMessageId(),
      timestamp: message.timestamp ?? new Date(),
    };
    setChatMessages((prev) => [...prev, newMessage]);
  }, []);

  const sendUserMessage = useCallback(
    async (content: string) => {
      addChatMessage({ type: 'user', content });

      const thinkingId = createClientMessageId('msg_thinking');
      setChatMessages((prev) => [
        ...prev,
        {
          id: thinkingId,
          type: 'agent' as const,
          content: '⏳ Working on it...',
          timestamp: new Date(),
        },
      ]);

      try {
        const response = workspaceId
          ? await sendWorkspaceMessage(workspaceId, content)
          : await sendChatMessage(
              trip.trip_id,
              content,
              chatMessagesRef.current
                .filter((m) => m.type === 'user' || m.type === 'agent')
                .filter((m) => !m.content.startsWith('⏳'))
                .slice(-10)
                .map((m) => ({ role: m.type === 'user' ? 'user' : 'agent', content: m.content })),
            );

        setChatMessages((prev) => prev.filter((m) => m.id !== thinkingId));

        response.messages.forEach((msg) => {
          if (msg.type === 'agent') {
            addChatMessage({ id: msg.id, timestamp: new Date(msg.timestamp), type: 'agent', content: msg.content });
          }
          if (msg.type === 'interrupt') {
            if (msg.interrupt_type === 'open_url' && msg.content) {
              window.open(msg.content, '_blank', 'noopener,noreferrer');
              return;
            }
            addChatMessage({
              id: msg.id,
              timestamp: new Date(msg.timestamp),
              type: 'interrupt',
              content: msg.content,
              interrupt_type: msg.interrupt_type as any,
              options: msg.options,
              status: msg.status as any,
            });
          }
        });

        if (response.updated_trip) {
          setTrip(response.updated_trip);
        }

        if (workspaceId) {
          await refreshWorkspaceSnapshot();
        }
      } catch {
        setChatMessages((prev) => prev.filter((m) => m.id !== thinkingId));
        addChatMessage({ type: 'agent', content: "Sorry, I'm having trouble connecting right now. Please try again." });
      }
    },
    [addChatMessage, trip.trip_id, workspaceId, refreshWorkspaceSnapshot],
  );

  const handleInterruptAction = useCallback(
    (messageId: string, action: 'approve' | 'reject', optionId?: string) => {
      const target = chatMessagesRef.current.find((msg) => msg.id === messageId);
      setChatMessages((prev) =>
        prev.map((msg) => {
          if (msg.id === messageId) {
            return { ...msg, status: action === 'approve' ? 'approved' : 'rejected' };
          }
          return msg;
        }),
      );

      const targetText = target?.content || '';
      const looksLikeBooking = /航班|机票|订票|trip\.com/i.test(targetText);
      if (action === 'approve' && optionId && (target?.interrupt_type === 'confirmation' || looksLikeBooking)) {
        sendUserMessage(`option_id: ${optionId}`);
        return;
      }

      setTimeout(() => {
        if (action === 'approve' && optionId) {
          addChatMessage({ type: 'agent', content: `Perfect! I've updated your itinerary with your selection. ✅` });
        } else {
          addChatMessage({ type: 'agent', content: `No problem! Let me find some other options for you... 🔄` });
        }
      }, 500);
    },
    [addChatMessage, sendUserMessage],
  );

  const createShareLink = useCallback(async () => {
    if (!workspaceId) return null;
    try {
      const res = await createWorkspaceShareLink(workspaceId);
      return `${window.location.origin}${res.url_path}`;
    } catch {
      return null;
    }
  }, [workspaceId]);

  const ingestWorkspaceUrls = useCallback(
    async (urls: string[]) => {
      if (!workspaceId) {
        throw new Error('Workspace ID is required for workspace ingest');
      }
      const result = await processWorkspaceVideos(workspaceId, urls);
      setTrip(result.snapshot.trip);
      setMediaByPlace(result.snapshot.media_by_place || {});
      setChatMessages(mapWorkspaceEventsToMessages(result.snapshot.recent_events || []));
      return { imported: result.imported_count, failed: result.failed_count };
    },
    [workspaceId],
  );

  return (
    <TripContext.Provider
      value={{
        trip,
        workspaceId,
        workspaceToken,
        selectedPOI,
        setSelectedPOI,
        chatMessages,
        addChatMessage,
        sendUserMessage,
        handleInterruptAction,
        isChatOpen,
        setIsChatOpen,
        activeView,
        setActiveView,
        isLoading,
        mediaByPlace,
        createShareLink,
        refreshWorkspaceSnapshot,
        ingestWorkspaceUrls,
      }}
    >
      {children}
    </TripContext.Provider>
  );
};
