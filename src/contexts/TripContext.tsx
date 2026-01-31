import React, { createContext, useContext, useState, useCallback, ReactNode } from 'react';
import { Trip, POI, ChatMessage, sampleTrip, initialChatMessages, mockChatResponses } from '@/data/mockData';

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
}

export const TripProvider: React.FC<TripProviderProps> = ({ children }) => {
  const [trip] = useState<Trip>(sampleTrip);
  const [selectedPOI, setSelectedPOI] = useState<POI | null>(null);
  const [chatMessages, setChatMessages] = useState<ChatMessage[]>(initialChatMessages);
  const [isChatOpen, setIsChatOpen] = useState(false);
  const [activeView, setActiveView] = useState<'map' | 'timeline' | 'cards'>('map');

  const addChatMessage = useCallback((message: Omit<ChatMessage, 'id' | 'timestamp'>) => {
    const newMessage: ChatMessage = {
      ...message,
      id: `msg_${Date.now()}`,
      timestamp: new Date(),
    };
    setChatMessages(prev => [...prev, newMessage]);
  }, []);

  const sendUserMessage = useCallback((content: string) => {
    // Add user message
    addChatMessage({ type: 'user', content });

    // Simulate AI response based on keywords
    setTimeout(() => {
      const lowerContent = content.toLowerCase();
      
      if (lowerContent.includes('cheaper') || lowerContent.includes('budget')) {
        setChatMessages(prev => [...prev, { ...mockChatResponses['cheaper hotel'], id: `msg_${Date.now()}`, timestamp: new Date() }]);
      } else if (lowerContent.includes('sushi') || lowerContent.includes('replace')) {
        setChatMessages(prev => [...prev, { ...mockChatResponses['sushi'], id: `msg_${Date.now()}`, timestamp: new Date() }]);
      } else if (lowerContent.includes('coffee') || lowerContent.includes('cafe')) {
        setChatMessages(prev => [...prev, { ...mockChatResponses['coffee'], id: `msg_${Date.now()}`, timestamp: new Date() }]);
      } else {
        addChatMessage({
          type: 'agent',
          content: "I'm on it! Let me search for the best options based on your saved videos... 🔍",
        });
      }
    }, 1000);
  }, [addChatMessage]);

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
      }}
    >
      {children}
    </TripContext.Provider>
  );
};
