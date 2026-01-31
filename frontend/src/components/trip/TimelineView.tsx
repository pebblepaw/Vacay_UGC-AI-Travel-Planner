import { motion } from 'framer-motion';
import { useTripContext } from '@/contexts/TripContext';
import { POI } from '@/data/mockData';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { Collapsible, CollapsibleContent, CollapsibleTrigger } from '@/components/ui/collapsible';
import {
  ChevronDown,
  Clock,
  MapPin,
  Utensils,
  Palette,
  Trees,
  Building2,
  ShoppingBag,
  PartyPopper,
  Home
} from 'lucide-react';
import { useState } from 'react';

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

export const TimelineView = () => {
  const { trip, selectedPOI, setSelectedPOI } = useTripContext();
  const [expandedDays, setExpandedDays] = useState<number[]>(
    trip.days.map((d) => d.day_number)
  );

  const toggleDay = (dayNumber: number) => {
    setExpandedDays((prev) =>
      prev.includes(dayNumber)
        ? prev.filter((d) => d !== dayNumber)
        : [...prev, dayNumber]
    );
  };

  return (
    <div className="space-y-4 pb-24">
      {trip.days.map((day, dayIndex) => (
        <Collapsible
          key={day.day_number}
          open={expandedDays.includes(day.day_number)}
          onOpenChange={() => toggleDay(day.day_number)}
        >
          <motion.div
            initial={{ opacity: 0, y: 20 }}
            animate={{ opacity: 1, y: 0 }}
            transition={{ delay: dayIndex * 0.1 }}
          >
            {/* Day Header */}
            <CollapsibleTrigger className="w-full">
              <div className="flex items-center justify-between p-4 bg-secondary/50 rounded-xl hover:bg-secondary transition-colors">
                <div className="flex items-center gap-3">
                  <div className="gradient-bg w-10 h-10 rounded-xl flex items-center justify-center">
                    <span className="text-primary-foreground font-bold">
                      {day.day_number}
                    </span>
                  </div>
                  <div className="text-left">
                    <h3 className="font-semibold text-foreground">
                      Day {day.day_number}
                    </h3>
                    <p className="text-sm text-muted-foreground">
                      {new Date(day.date).toLocaleDateString('en-US', {
                        weekday: 'long',
                        month: 'short',
                        day: 'numeric',
                      })}
                    </p>
                  </div>
                </div>
                <div className="flex items-center gap-2">
                  <Badge variant="secondary">
                    {day.pois.length} stops
                  </Badge>
                  <ChevronDown
                    className={`h-5 w-5 text-muted-foreground transition-transform ${expandedDays.includes(day.day_number) ? 'rotate-180' : ''
                      }`}
                  />
                </div>
              </div>
            </CollapsibleTrigger>

            {/* Day Content */}
            <CollapsibleContent>
              <div className="relative mt-4 ml-5 pl-6 border-l-2 border-border">
                {day.pois.map((poi, poiIndex) => {
                  const Icon = categoryIcons[poi.category];
                  const isSelected = selectedPOI?.id === poi.id;

                  return (
                    <motion.div
                      key={poi.id}
                      initial={{ opacity: 0, x: -20 }}
                      animate={{ opacity: 1, x: 0 }}
                      transition={{ delay: poiIndex * 0.05 }}
                      className="relative mb-6 last:mb-0"
                    >
                      {/* Timeline dot */}
                      <div
                        className={`absolute -left-[31px] w-4 h-4 rounded-full ${categoryColors[poi.category]} border-2 border-background`}
                      />

                      {/* POI Card */}
                      <Card
                        className={`overflow-hidden cursor-pointer transition-all hover:shadow-card ${isSelected
                            ? 'ring-2 ring-primary shadow-glow'
                            : ''
                          }`}
                        onClick={() => setSelectedPOI(poi)}
                      >
                        <div className="flex">
                          {/* Image */}
                          <div className="relative w-24 h-24 sm:w-32 sm:h-32 flex-shrink-0">
                            <img
                              src={poi.img}
                              alt={poi.name}
                              className="w-full h-full object-cover"
                              onError={(e) => {
                                e.currentTarget.src = `https://placehold.co/128x128/1a1a2e/eaeaea?text=${encodeURIComponent(poi.name.slice(0, 15))}`;
                              }}
                            />
                            <div
                              className={`absolute top-2 left-2 p-1.5 rounded-lg ${categoryColors[poi.category]}`}
                            >
                              <Icon className="h-3 w-3 text-primary-foreground" />
                            </div>
                          </div>

                          {/* Content */}
                          <CardContent className="flex-1 p-3 sm:p-4">
                            <div className="flex items-start justify-between gap-2 mb-1">
                              <h4 className="font-semibold text-foreground text-sm sm:text-base line-clamp-1">
                                {poi.name}
                              </h4>
                              <Badge variant="secondary" className="text-xs shrink-0">
                                {poi.category}
                              </Badge>
                            </div>

                            <div className="flex items-center gap-2 text-xs text-muted-foreground mb-2">
                              <Clock className="h-3 w-3" />
                              {poi.time_slot}
                            </div>

                            <p className="text-xs sm:text-sm text-muted-foreground line-clamp-2">
                              {poi.vibe}
                            </p>
                          </CardContent>
                        </div>
                      </Card>

                      {/* Travel time indicator */}
                      {poi.travel_time && poiIndex < day.pois.length - 1 && (
                        <div className="flex items-center gap-2 mt-3 ml-4 text-xs text-muted-foreground">
                          <div className="h-px flex-1 bg-border max-w-16" />
                          <span>{poi.travel_time}</span>
                          <div className="h-px flex-1 bg-border max-w-16" />
                        </div>
                      )}
                    </motion.div>
                  );
                })}

                {/* Accommodation at end of day */}
                {dayIndex === trip.days.length - 1 && (
                  <motion.div
                    initial={{ opacity: 0, x: -20 }}
                    animate={{ opacity: 1, x: 0 }}
                    className="relative"
                  >
                    <div className="absolute -left-[31px] w-4 h-4 rounded-full bg-primary border-2 border-background" />

                    <Card className="overflow-hidden bg-secondary/30">
                      <div className="flex">
                        <div className="relative w-24 h-24 sm:w-32 sm:h-32 flex-shrink-0">
                          <img
                            src={trip.accommodation.img}
                            alt={trip.accommodation.name}
                            className="w-full h-full object-cover"
                            onError={(e) => {
                              e.currentTarget.src = `https://placehold.co/128x128/1a1a2e/eaeaea?text=${encodeURIComponent(trip.accommodation.name.slice(0, 15))}`;
                            }}
                          />
                          <div className="absolute top-2 left-2 p-1.5 rounded-lg bg-primary">
                            <Home className="h-3 w-3 text-primary-foreground" />
                          </div>
                        </div>
                        <CardContent className="flex-1 p-3 sm:p-4">
                          <div className="flex items-center gap-2 mb-1">
                            <h4 className="font-semibold text-foreground text-sm sm:text-base">
                              {trip.accommodation.name}
                            </h4>
                          </div>
                          <p className="text-sm font-medium text-primary">
                            ${trip.accommodation.price_per_night}/night
                          </p>
                          <p className="text-xs text-muted-foreground mt-1">
                            {trip.accommodation.status}
                          </p>
                        </CardContent>
                      </div>
                    </Card>
                  </motion.div>
                )}
              </div>
            </CollapsibleContent>
          </motion.div>
        </Collapsible>
      ))}
    </div>
  );
};
