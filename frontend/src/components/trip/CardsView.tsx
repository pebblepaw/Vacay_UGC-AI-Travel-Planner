import { useRef } from 'react';
import { motion } from 'framer-motion';
import { useTripContext } from '@/contexts/TripContext';
import { POI } from '@/data/mockData';
import { Badge } from '@/components/ui/badge';
import {
  Clock,
  MapPin,
  Utensils,
  Palette,
  Trees,
  Building2,
  ShoppingBag,
  PartyPopper,
  ChevronLeft,
  ChevronRight
} from 'lucide-react';
import { Button } from '@/components/ui/button';

const categoryIcons: Record<POI['category'], typeof MapPin> = {
  Food: Utensils,
  Art: Palette,
  Nature: Trees,
  Culture: Building2,
  Shopping: ShoppingBag,
  Nightlife: PartyPopper,
};

const categoryColors: Record<POI['category'], string> = {
  Food: 'bg-category-food',
  Art: 'bg-category-art',
  Nature: 'bg-category-nature',
  Culture: 'bg-category-culture',
  Shopping: 'bg-category-shopping',
  Nightlife: 'bg-category-nightlife',
};

export const CardsView = () => {
  const { trip, selectedPOI, setSelectedPOI } = useTripContext();
  const scrollContainerRef = useRef<HTMLDivElement>(null);

  const allPOIs = trip.days.flatMap((day, dayIndex) =>
    day.pois.map((poi) => ({ ...poi, dayNumber: dayIndex + 1 }))
  );

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = direction === 'left' ? -320 : 320;
      scrollContainerRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  return (
    <div className="space-y-6 pb-24">
      {/* Header */}
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">All Destinations</h2>
          <p className="text-sm text-muted-foreground">
            {allPOIs.length} amazing spots from your saved videos
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button
            variant="outline"
            size="icon"
            className="rounded-full"
            onClick={() => scroll('left')}
          >
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button
            variant="outline"
            size="icon"
            className="rounded-full"
            onClick={() => scroll('right')}
          >
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      {/* Horizontal Scroll Cards */}
      <div
        ref={scrollContainerRef}
        className="flex gap-4 overflow-x-auto hide-scrollbar snap-x snap-mandatory pb-4 -mx-4 px-4"
      >
        {allPOIs.map((poi, index) => {
          const Icon = categoryIcons[poi.category];
          const isSelected = selectedPOI?.id === poi.id;

          return (
            <motion.div
              key={poi.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              whileHover={{ y: -8 }}
              onClick={() => setSelectedPOI(poi)}
              className={`relative flex-shrink-0 w-72 snap-center cursor-pointer rounded-2xl overflow-hidden glass shadow-card transition-all ${isSelected ? 'ring-2 ring-primary shadow-glow' : ''
                }`}
            >
              {/* Image */}
              <div className="relative h-48">
                <img
                  src={poi.img}
                  alt={poi.name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.src = `https://placehold.co/600x400/1a1a2e/eaeaea?text=${encodeURIComponent(poi.name.slice(0, 20))}`;
                  }}
                />

                {/* Gradient overlay */}
                <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-transparent to-transparent" />

                {/* Category badge */}
                <div className="absolute top-3 left-3">
                  <Badge className={`${categoryColors[poi.category]} text-primary-foreground gap-1`}>
                    <Icon className="h-3 w-3" />
                    {poi.category}
                  </Badge>
                </div>

                {/* Day badge */}
                <div className="absolute top-3 right-3">
                  <Badge variant="secondary" className="glass">
                    Day {poi.dayNumber}
                  </Badge>
                </div>

                {/* Title overlay */}
                <div className="absolute bottom-3 left-3 right-3">
                  <h3 className="text-lg font-bold text-foreground mb-1">
                    {poi.name}
                  </h3>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {poi.time_slot}
                  </div>
                </div>
              </div>

              {/* Content */}
              <div className="p-4">
                <p className="text-sm text-muted-foreground line-clamp-3">
                  {poi.vibe}
                </p>

                {poi.travel_time && (
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {poi.travel_time} to next stop
                  </div>
                )}
              </div>

              {/* Hover effect */}
              <motion.div
                initial={{ opacity: 0 }}
                whileHover={{ opacity: 1 }}
                className="absolute inset-0 bg-primary/5 pointer-events-none"
              />
            </motion.div>
          );
        })}
      </div>

      {/* Grid View for larger screens */}
      <div className="hidden md:grid md:grid-cols-2 lg:grid-cols-3 gap-4">
        {allPOIs.map((poi, index) => {
          const Icon = categoryIcons[poi.category];
          const isSelected = selectedPOI?.id === poi.id;

          return (
            <motion.div
              key={`grid-${poi.id}`}
              initial={{ opacity: 0, y: 20 }}
              animate={{ opacity: 1, y: 0 }}
              transition={{ delay: index * 0.03 }}
              whileHover={{ y: -4 }}
              onClick={() => setSelectedPOI(poi)}
              className={`cursor-pointer rounded-xl overflow-hidden bg-card shadow-sm hover:shadow-card transition-all ${isSelected ? 'ring-2 ring-primary' : ''
                }`}
            >
              <div className="relative h-40">
                <img
                  src={poi.img}
                  alt={poi.name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.src = `https://placehold.co/600x400/1a1a2e/eaeaea?text=${encodeURIComponent(poi.name.slice(0, 20))}`;
                  }}
                />
                <div className="absolute top-2 left-2">
                  <Badge className={`${categoryColors[poi.category]} text-primary-foreground text-xs gap-1`}>
                    <Icon className="h-3 w-3" />
                    {poi.category}
                  </Badge>
                </div>
                <div className="absolute top-2 right-2">
                  <Badge variant="secondary" className="text-xs">
                    Day {poi.dayNumber}
                  </Badge>
                </div>
              </div>
              <div className="p-3">
                <h4 className="font-semibold text-foreground mb-1 line-clamp-1">
                  {poi.name}
                </h4>
                <p className="text-xs text-muted-foreground line-clamp-2">
                  {poi.vibe}
                </p>
              </div>
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
