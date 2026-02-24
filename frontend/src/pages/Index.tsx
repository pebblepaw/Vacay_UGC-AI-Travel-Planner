import { TripProvider, useTripContext } from '@/contexts/TripContext';
import { TripHeader } from '@/components/trip/TripHeader';
import { ViewTabs } from '@/components/trip/ViewTabs';
import { MapView } from '@/components/trip/MapView';
import { TimelineView } from '@/components/trip/TimelineView';
import { CardsView } from '@/components/trip/CardsView';
import { ChatSidebar } from '@/components/trip/ChatSidebar';
import { AddUrlModal } from '@/components/trip/AddUrlModal';
import { motion, AnimatePresence } from 'framer-motion';
import { useSearchParams } from 'react-router-dom';

const TripContent = () => {
  const { activeView, isLoading } = useTripContext();

  if (isLoading) {
    return (
      <div className="flex items-center justify-center min-h-screen">
        <div className="text-center">
          <div className="animate-spin rounded-full h-12 w-12 border-b-2 border-primary mx-auto mb-4"></div>
          <p className="text-muted-foreground">Loading your trip...</p>
        </div>
      </div>
    );
  }

  return (
    <div className="flex flex-col min-h-screen bg-background">
      <TripHeader />

      <main className="flex-1 flex flex-col lg:flex-row">
        {/* Map Section - Fixed on desktop, toggleable on mobile */}
        <div className="lg:w-[60%] h-[40vh] lg:h-[calc(100vh-73px)] lg:sticky lg:top-[73px]">
          <div className="h-full p-4">
            <MapView />
          </div>
        </div>

        {/* Content Section */}
        <div className="flex-1 lg:w-[40%] flex flex-col">
          {/* View Tabs */}
          <div className="sticky top-[73px] z-30 bg-background/80 backdrop-blur-lg py-4 px-4">
            <ViewTabs />
          </div>

          {/* Content Area */}
          <div className="flex-1 px-4 overflow-hidden">
            <AnimatePresence mode="wait">
              {activeView === 'timeline' && (
                <motion.div
                  key="timeline"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="h-full"
                >
                  <TimelineView />
                </motion.div>
              )}
              {activeView === 'cards' && (
                <motion.div
                  key="cards"
                  initial={{ opacity: 0, y: 20 }}
                  animate={{ opacity: 1, y: 0 }}
                  exit={{ opacity: 0, y: -20 }}
                  className="h-full"
                >
                  <CardsView />
                </motion.div>
              )}
            </AnimatePresence>
          </div>
        </div>
      </main>

      {/* Floating elements */}
      <ChatSidebar />
      <AddUrlModal />
    </div>
  );
};

const Index = () => {
  const [searchParams] = useSearchParams();
  const tripId = searchParams.get('trip');

  return (
    <TripProvider tripId={tripId || undefined}>
      <TripContent />
    </TripProvider>
  );
};

export default Index;
