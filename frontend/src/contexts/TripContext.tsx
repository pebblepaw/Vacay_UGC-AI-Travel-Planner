import React, { createContext, useContext, useState, useCallback, ReactNode, useEffect } from 'react';
import { Trip, POI, ChatMessage, sampleTrip, initialChatMessages } from '@/data/mockData';
import { getTrip, sendChatMessage } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

interface TripContextType {
  trip: Trip;
  selectedPOI: POI | null;
  setSelectedPOI: (poi: POI | null) => void;
  chatMessages: ChatMessage[];
  addChatMessage: (message: Omit<ChatMessage, 'id' | 'timestamp'>) => void;
  sendUserMessage: (content: string) => void;
  handleInterruptAction: (messageId: string, action: 'approve' | 'reject', optionId?: string) => void;
  isChatOpen: boolean;
  setIsChatOpen: (open: boolean) => void;
  activeView: 'map' | 'timeline' | 'cards';
  setActiveView: (view: 'map' | 'timeline' | 'cards') => void;
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
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeView, setActiveView] = useState<'map' | 'timeline' | 'cards'>('map');
  const [isLoading, setIsLoading] = useState(false);
  const { toast } = useToast();

  // Load trip from backend if tripId provided
  useEffect(() => {
    if (tripId) {
      setIsLoading(true);
      getTrip(tripId)
        .then((data) => {
          setTrip(data);
          // Add initial greeting from AI
          setChatMessages([{
            id: `msg_${Date.now()}`,
            type: 'agent',
            content: `Hey! 👋 I've loaded your trip "${data.title}". Feel free to ask me anything!`,
            timestamp: new Date(),
          }]);
        })
        .catch((error) => {
          toast({
            variant: 'destructive',
            title: 'Error loading trip',
            description: error.message,
          });
        })
        .finally(() => setIsLoading(false));
    }
  }, [tripId, toast]);

  const addChatMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: `msg_${Date.now()}`,
      timestamp: new Date(),
    };
    setChatMessages(prev => [...prev, newMessage]);
  }, []);

  const sendUserMessage = useCallback(async (content: string) => {
    // Add user message
    addChatMessage({ type: 'user', content });

    // Show thinking indicator immediately
    const thinkingId = `msg_thinking_${Date.now()}`;
    setChatMessages(prev => [...prev, {
      id: thinkingId,
      type: 'agent' as const,
      content: '⏳ Working on it...',
      timestamp: new Date(),
    }]);

    try {
      // Call backend API
      const response = await sendChatMessage(trip.trip_id, content);

      // Remove thinking message
      setChatMessages(prev => prev.filter(m => m.id !== thinkingId));
      
      // Add agent response(s)
      response.messages.forEach((msg) => {
        if (msg.type === 'agent') {
          addChatMessage({
            type: 'agent',
            content: msg.content,
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
    setChatMessages(prev => prev.map(msg => {
      if (msg.id === messageId) {
        return { ...msg, status: action === 'approve' ? 'approved' : 'rejected' };
      }
      return msg;
    }));

    // Add follow-up message
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
  }, [addChatMessage]);

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
