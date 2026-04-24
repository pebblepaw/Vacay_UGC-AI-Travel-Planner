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
  ChevronRight,
  FolderOpen,
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

const toEmbed = (url: string) => {
  if (url.includes('youtube.com') || url.includes('youtu.be')) {
    const match = url.match(/(?:v=|youtu\.be\/)([\w-]+)/);
    if (match?.[1]) return `https://www.youtube.com/embed/${match[1]}?autoplay=1&mute=1&loop=1&playlist=${match[1]}`;
  }
  return null;
};

const canRenderVideoTag = (url: string, platform: string) => {
  if (platform === 'instagram' || platform === 'tiktok') return false;
  return /\.(mp4|webm|ogg)(\?|$)/i.test(url);
};

export const CardsView = () => {
  const { trip, selectedPOI, setSelectedPOI, mediaByPlace } = useTripContext();
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
      <div className="flex items-center justify-between">
        <div>
          <h2 className="text-xl font-semibold text-foreground">All Destinations</h2>
          <p className="text-sm text-muted-foreground">
            {allPOIs.length} amazing spots from your saved videos
          </p>
        </div>
        <div className="flex items-center gap-2">
          <Button variant="outline" size="icon" className="rounded-full" onClick={() => scroll('left')}>
            <ChevronLeft className="h-4 w-4" />
          </Button>
          <Button variant="outline" size="icon" className="rounded-full" onClick={() => scroll('right')}>
            <ChevronRight className="h-4 w-4" />
          </Button>
        </div>
      </div>

      <div ref={scrollContainerRef} className="flex gap-4 overflow-x-auto hide-scrollbar snap-x snap-mandatory pb-4 -mx-4 px-4">
        {allPOIs.map((poi, index) => {
          const Icon = categoryIcons[poi.category];
          const isSelected = selectedPOI?.id === poi.id;
          const media = mediaByPlace[poi.id] || [];

          return (
            <motion.div
              key={poi.id}
              initial={{ opacity: 0, scale: 0.9 }}
              animate={{ opacity: 1, scale: 1 }}
              transition={{ delay: index * 0.05 }}
              whileHover={{ y: -8 }}
              onClick={() => setSelectedPOI(poi)}
              className={`relative flex-shrink-0 w-72 snap-center cursor-pointer rounded-2xl overflow-hidden glass shadow-card transition-all ${isSelected ? 'ring-2 ring-primary shadow-glow' : ''}`}
            >
              <div className="relative h-48">
                <img
                  src={poi.img}
                  alt={poi.name}
                  className="w-full h-full object-cover"
                  onError={(e) => {
                    e.currentTarget.src = `https://placehold.co/600x400/1a1a2e/eaeaea?text=${encodeURIComponent(poi.name.slice(0, 20))}`;
                  }}
                />

                <div className="absolute inset-0 bg-gradient-to-t from-background/90 via-transparent to-transparent" />

                <div className="absolute top-3 left-3">
                  <Badge className={`${categoryColors[poi.category]} text-primary-foreground gap-1`}>
                    <Icon className="h-3 w-3" />
                    {poi.category}
                  </Badge>
                </div>

                <div className="absolute top-3 right-3">
                  <Badge variant="secondary" className="glass">Day {poi.dayNumber}</Badge>
                </div>

                <div className="absolute bottom-3 left-3 right-3">
                  <h3 className="text-lg font-bold text-foreground mb-1">{poi.name}</h3>
                  <div className="flex items-center gap-2 text-sm text-muted-foreground">
                    <Clock className="h-3 w-3" />
                    {poi.time_slot}
                  </div>
                </div>
              </div>

              <div className="p-4 space-y-2">
                <p className="text-sm text-muted-foreground line-clamp-3">{poi.vibe}</p>

                {media.length > 0 && (
                  <div className="space-y-2 border rounded-lg p-2 bg-background/70">
                    <div className="text-xs font-medium flex items-center gap-1">
                      <FolderOpen className="h-3 w-3" />
                      Media folder ({media.length})
                    </div>
                    <div className="space-y-2 max-h-36 overflow-y-auto">
                      {media.slice(0, 3).map((item, idx) => {
                        const embed = toEmbed(item.url);
                        return (
                          <div key={`${poi.id}-media-${idx}`} className="rounded-md border p-1 text-xs">
                            <div className="line-clamp-1 mb-1">{item.title}</div>
                            {embed ? (
                              <iframe
                                src={embed}
                                title={item.title}
                                className="w-full h-20 rounded"
                                allow="autoplay; encrypted-media"
                              />
                            ) : canRenderVideoTag(item.url, item.platform) ? (
                              <video className="w-full h-20 rounded object-cover" autoPlay muted loop playsInline>
                                <source src={item.url} />
                              </video>
                            ) : (
                              <a
                                href={item.url}
                                target="_blank"
                                rel="noreferrer"
                                className="w-full h-20 rounded border bg-muted/50 flex items-center justify-center text-center px-2"
                              >
                                <span className="text-[11px]">{item.platform.toUpperCase()} · Open source link</span>
                              </a>
                            )}
                          </div>
                        );
                      })}
                    </div>
                  </div>
                )}

                {poi.travel_time && (
                  <div className="flex items-center gap-2 mt-3 pt-3 border-t border-border text-xs text-muted-foreground">
                    <MapPin className="h-3 w-3" />
                    {poi.travel_time} to next stop
                  </div>
                )}
              </div>

              <motion.div initial={{ opacity: 0 }} whileHover={{ opacity: 1 }} className="absolute inset-0 bg-primary/5 pointer-events-none" />
            </motion.div>
          );
        })}
      </div>
    </div>
  );
};
