import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect, useRef } from 'react';
import { Trip, POI, ChatMessage, sampleTrip, initialChatMessages } from '@/data/mockData';
import { getTrip, sendChatMessage, listTrips } from '@/lib/api';
import { createClientMessageId, PendingChatMessage } from '@/lib/chatMessages';
import { useToast } from '@/hooks/use-toast';

interface TripContextType {
  trip: Trip;
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
}

export const TripProvider: React.FC<TripProviderProps> = ({ children, tripId }) => {
  const [trip, setTrip] = useState<Trip>(sampleTrip);
  const [selectedPOI, setSelectedPOI] = useState<POI | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(initialChatMessages);
  const chatMessagesRef = useRef<ChatMessage[]>(initialChatMessages);

  // Keep ref in sync with state
  useEffect(() => {
    chatMessagesRef.current = chatMessages;
  }, [chatMessages]);

  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeView, setActiveView] = useState<'timeline' | 'cards'>('timeline');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Load trip from backend — by tripId, or fetch the most recent trip
  useEffect(() => {
    const loadTrip = async (id: string) => {
      setIsLoading(true);
      try {
        const data = await getTrip(id);
        setTrip(data);
            setChatMessages([{
              id: createClientMessageId(),
              type: 'agent',
              content: `Hey! 👋 I've loaded your trip "${data.title}". Feel free to ask me anything!`,
              timestamp: new Date(),
        }]);
      } catch (error: any) {
        toast({
          variant: 'destructive',
          title: 'Error loading trip',
          description: error.message,
        });
      } finally {
        setIsLoading(false);
      }
    };

    if (tripId) {
      loadTrip(tripId);
    } else {
      // No trip param — load the most recent trip from Supabase
      setIsLoading(true);
      listTrips()
        .then((data) => {
          if (data.trips && data.trips.length > 0) {
            const latest = data.trips[0];
            setTrip(latest);
            setChatMessages([{
              id: createClientMessageId(),
              type: 'agent',
              content: `Hey! 👋 I've loaded your trip "${latest.title}". Feel free to ask me anything!`,
              timestamp: new Date(),
            }]);
          }
          // If no trips exist, keep the sampleTrip default
        })
        .catch(() => {
          // Backend not available — keep sampleTrip default
        })
        .finally(() => setIsLoading(false));
    }
  }, [tripId, toast]);

  const addChatMessage = useCallback((message: PendingChatMessage) => {
    const newMessage: ChatMessage = {
      ...message,
      id: message.id ?? createClientMessageId(),
      timestamp: message.timestamp ?? new Date(),
    };
    setChatMessages(prev => [...prev, newMessage]);
  }, []);

  const sendUserMessage = useCallback(async (content: string) => {
    // Add user message
    addChatMessage({ type: 'user', content });

    // Build history from existing chat messages (excluding thinking indicators)
    // Using functional ref to get latest messages at call time
    const currentMessages = chatMessagesRef.current;
    const history = currentMessages
      .filter(m => m.type === 'user' || m.type === 'agent')
      .filter(m => !m.content.startsWith('⏳'))
      .slice(-10) // Last 10 messages
      .map(m => ({
        role: m.type === 'user' ? 'user' : 'agent',
        content: m.content,
      }));

    // Show thinking indicator immediately
    const thinkingId = createClientMessageId('msg_thinking');
    setChatMessages(prev => [...prev, {
      id: thinkingId,
      type: 'agent' as const,
      content: '⏳ Working on it...',
      timestamp: new Date(),
    }]);

    try {
      // Call backend API with history
      const response = await sendChatMessage(trip.trip_id, content, history);

      // Remove thinking message
      setChatMessages(prev => prev.filter(m => m.id !== thinkingId));
      
      // Add agent response(s)
      response.messages.forEach((msg) => {
        if (msg.type === 'agent') {
          addChatMessage({
            id: msg.id,
            timestamp: new Date(msg.timestamp),
            type: 'agent',
            content: msg.content,
          });
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
            interrupt_type: msg.interrupt_type,
            options: msg.options,
            status: msg.status,
          });
        }
      });

      // Update trip state if backend returned changes
      if (response.updated_trip) {
        setTrip(response.updated_trip);
      }
    } catch (error) {
      // Remove thinking message and show error
      setChatMessages(prev => prev.filter(m => m.id !== thinkingId));
      addChatMessage({
        type: 'agent',
        content: "Sorry, I'm having trouble connecting right now. Please try again.",
      });
    }
  }, [addChatMessage, trip.trip_id]);

  const handleInterruptAction = useCallback((messageId: string, action: 'approve' | 'reject', optionId?: string) => {
    const target = chatMessagesRef.current.find(msg => msg.id === messageId);
    setChatMessages(prev => prev.map(msg => {
      if (msg.id === messageId) {
        return { ...msg, status: action === 'approve' ? 'approved' : 'rejected' };
      }
      return msg;
    }));

    const targetText = target?.content || '';
    const looksLikeBooking = /航班|机票|订票|trip\.com/i.test(targetText);
    if (action === 'approve' && optionId && (target?.interrupt_type === 'confirmation' || looksLikeBooking)) {
      sendUserMessage(`option_id: ${optionId}`);
      return;
    }

    setTimeout(() => {
      if (action === 'approve' && optionId) {
        addChatMessage({
          type: 'agent',
          content: `Perfect! I've updated your itinerary with your selection. ✅`,
        });
      } else {
        addChatMessage({
          type: 'agent',
          content: `No problem! Let me find some other options for you... 🔄`,
        });
      }
    }, 500);
  }, [addChatMessage, sendUserMessage]);

  return (
    <TripContext.Provider
      value={{
        trip,
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
      }}
    >
      {children}
    </TripContext.Provider>
  );
};
