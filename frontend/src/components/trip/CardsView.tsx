import { useRef, useState } from 'react';
import { motion } from 'framer-motion';
import { useTripContext } from '@/contexts/TripContext';
import { POI } from '@/data/mockData';
import { Badge } from '@/components/ui/badge';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogTitle,
} from '@/components/ui/dialog';
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
  ExternalLink,
  Play,
} from 'lucide-react';
import { Button } from '@/components/ui/button';

type PlaceMedia = {
  title: string;
  url: string;
  source_url?: string;
  platform: string;
  autoplay: boolean;
};

type CardPOI = POI & { dayNumber: number };

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

export const canRenderVideoTag = (url: string, platform: string) => {
  if (/\.(mp4|webm|ogg)(\?|$)/i.test(url)) return true;
  if (platform === 'instagram' || platform === 'tiktok' || platform === 'douyin' || platform === 'rednote') return false;
  return false;
};

export const canRenderImageTag = (url: string) => /\.(png|jpe?g|gif|webp|avif)(\?|$)/i.test(url);

const renderMediaFrame = (item: PlaceMedia, className: string, autoplay = true) => {
  const embed = toEmbed(item.url);
  if (embed) {
    return (
      <iframe
        src={embed}
        title={item.title}
        className={className}
        allow="autoplay; encrypted-media; picture-in-picture"
        allowFullScreen
      />
    );
  }
  if (canRenderVideoTag(item.url, item.platform)) {
    return (
      <video
        key={item.url}
        className={className}
        autoPlay={autoplay}
        muted
        loop
        playsInline
        controls
      >
        <source src={item.url} />
      </video>
    );
  }
  if (canRenderImageTag(item.url)) {
    return <img src={item.url} alt={item.title} className={className} loading="lazy" />;
  }
  return (
    <a
      href={item.source_url || item.url}
      target="_blank"
      rel="noreferrer"
      aria-label={`Open original ${item.platform} source`}
      className={`${className} flex flex-col items-center justify-center gap-3 border border-dashed border-border bg-muted/50 p-6 text-center transition-colors hover:bg-muted`}
    >
      <ExternalLink className="h-8 w-8 text-muted-foreground" />
      <span className="text-sm font-semibold text-foreground">Open original {item.platform} source</span>
      <span className="max-w-sm truncate text-xs text-muted-foreground">{item.source_url || item.url}</span>
    </a>
  );
};

export const CardsView = () => {
  const { trip, selectedPOI, setSelectedPOI, mediaByPlace } = useTripContext();
  const scrollContainerRef = useRef<HTMLDivElement>(null);
  const [mediaOverlay, setMediaOverlay] = useState<{
    poi: CardPOI;
    media: PlaceMedia[];
    selectedIndex: number;
  } | null>(null);

  const allPOIs = trip.days.flatMap((day, dayIndex) =>
    day.pois.map((poi) => ({ ...poi, dayNumber: dayIndex + 1 }))
  );

  const scroll = (direction: 'left' | 'right') => {
    if (scrollContainerRef.current) {
      const scrollAmount = direction === 'left' ? -320 : 320;
      scrollContainerRef.current.scrollBy({ left: scrollAmount, behavior: 'smooth' });
    }
  };

  const selectedMedia = mediaOverlay?.media[mediaOverlay.selectedIndex] || null;

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
              className={`relative flex-shrink-0 w-72 snap-center cursor-pointer overflow-hidden rounded-xl border border-border/70 bg-card shadow-sm transition-all ${isSelected ? 'ring-2 ring-primary shadow-glow' : ''}`}
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

              <div className="p-4 space-y-3">
                <p className="text-sm text-muted-foreground line-clamp-3">{poi.vibe}</p>

                {media.length > 0 && (
                  <button
                    type="button"
                    aria-label={`Open media folder for ${poi.name}`}
                    onClick={(event) => {
                      event.stopPropagation();
                      setMediaOverlay({ poi, media, selectedIndex: 0 });
                    }}
                    className="group w-full rounded-xl border border-border bg-background/80 p-3 text-left transition-all hover:-translate-y-0.5 hover:border-primary/60 hover:bg-background focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-ring"
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div className="flex items-center gap-2 text-sm font-semibold">
                        <FolderOpen className="h-4 w-4" />
                        Media folder
                      </div>
                      <Badge variant="secondary" className="rounded-full">
                        {media.length}
                      </Badge>
                    </div>
                    <div className="mt-3 grid grid-cols-[1fr_1fr_1fr] gap-2">
                      {media.slice(0, 3).map((item, idx) => (
                        <div
                          key={`${poi.id}-media-thumb-${idx}`}
                          className="relative h-16 overflow-hidden rounded-lg bg-muted"
                        >
                          {canRenderImageTag(item.url) ? (
                            <img src={item.url} alt="" className="h-full w-full object-cover" loading="lazy" />
                          ) : canRenderVideoTag(item.url, item.platform) || toEmbed(item.url) ? (
                            <div className="flex h-full w-full items-center justify-center bg-foreground/10">
                              <Play className="h-5 w-5 text-foreground" />
                            </div>
                          ) : (
                            <div className="flex h-full w-full items-center justify-center bg-muted text-[10px] font-semibold uppercase text-muted-foreground">
                              {item.platform}
                            </div>
                          )}
                          {idx === 2 && media.length > 3 && (
                            <div className="absolute inset-0 flex items-center justify-center bg-background/75 text-sm font-bold">
                              +{media.length - 2}
                            </div>
                          )}
                        </div>
                      ))}
                    </div>
                  </button>
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

      <Dialog open={Boolean(mediaOverlay)} onOpenChange={(open) => !open && setMediaOverlay(null)}>
        <DialogContent className="max-h-[90vh] max-w-5xl overflow-hidden rounded-2xl border-border bg-background p-0 shadow-2xl">
          {mediaOverlay && selectedMedia && (
            <div className="grid min-h-[520px] grid-rows-[auto_1fr] lg:grid-cols-[minmax(0,1fr)_280px] lg:grid-rows-1">
              <div className="flex min-h-[360px] flex-col bg-foreground/5">
                <div className="border-b border-border bg-background/95 px-5 py-4">
                  <DialogTitle className="text-xl">{mediaOverlay.poi.name}</DialogTitle>
                  <DialogDescription>
                    Day {mediaOverlay.poi.dayNumber} · {mediaOverlay.media.length} media item{mediaOverlay.media.length === 1 ? '' : 's'}
                  </DialogDescription>
                </div>
                <div className="flex min-h-0 flex-1 items-center justify-center p-4">
                  {renderMediaFrame(selectedMedia, 'max-h-[62vh] w-full rounded-xl object-contain lg:h-[62vh]')}
                </div>
              </div>

              <aside className="border-t border-border bg-card/70 p-4 lg:border-l lg:border-t-0">
                <div className="mb-4">
                  <div className="text-xs font-semibold uppercase tracking-wide text-muted-foreground">
                    Now playing
                  </div>
                  <div className="mt-1 line-clamp-2 text-sm font-semibold">{selectedMedia.title}</div>
                </div>
                <div className="flex max-h-60 gap-3 overflow-x-auto pb-1 lg:max-h-[420px] lg:flex-col lg:overflow-y-auto lg:overflow-x-hidden">
                  {mediaOverlay.media.map((item, idx) => (
                    <button
                      key={`${mediaOverlay.poi.id}-overlay-media-${idx}`}
                      type="button"
                      onClick={() => setMediaOverlay({ ...mediaOverlay, selectedIndex: idx })}
                      className={`min-w-44 rounded-xl border p-2 text-left transition-colors lg:min-w-0 ${
                        idx === mediaOverlay.selectedIndex
                          ? 'border-primary bg-primary/10'
                          : 'border-border bg-background hover:border-primary/50'
                      }`}
                    >
                      <div className="flex items-center gap-3">
                        <div className="flex h-14 w-16 flex-shrink-0 items-center justify-center overflow-hidden rounded-lg bg-muted">
                          {canRenderImageTag(item.url) ? (
                            <img src={item.url} alt="" className="h-full w-full object-cover" loading="lazy" />
                          ) : canRenderVideoTag(item.url, item.platform) || toEmbed(item.url) ? (
                            <Play className="h-5 w-5" />
                          ) : (
                            <ExternalLink className="h-5 w-5" />
                          )}
                        </div>
                        <div className="min-w-0">
                          <div className="line-clamp-2 text-xs font-semibold">{item.title}</div>
                          <div className="mt-1 text-[11px] uppercase tracking-wide text-muted-foreground">
                            {item.platform}
                          </div>
                        </div>
                      </div>
                    </button>
                  ))}
                </div>
              </aside>
            </div>
          )}
        </DialogContent>
      </Dialog>
    </div>
  );
};
