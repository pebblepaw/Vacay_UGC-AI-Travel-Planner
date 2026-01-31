import { useCallback } from 'react';
import { motion } from 'framer-motion';
import { useTripContext } from '@/contexts/TripContext';
import { POI } from '@/data/mockData';
import { Badge } from '@/components/ui/badge';
import { MapPin, Utensils, Palette, Trees, Building2, ShoppingBag, PartyPopper, ExternalLink } from 'lucide-react';
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

export const MapView = () => {
  const { trip, selectedPOI, setSelectedPOI } = useTripContext();

  const allPOIs = trip.days.flatMap((day) => day.pois);

  // Calculate map center from POI coordinates
  const validPOIs = allPOIs.filter(poi => poi.coords[0] !== 0 && poi.coords[1] !== 0);
  const center = validPOIs.length > 0 ? {
    lat: validPOIs.reduce((sum, poi) => sum + poi.coords[1], 0) / validPOIs.length,
    lng: validPOIs.reduce((sum, poi) => sum + poi.coords[0], 0) / validPOIs.length,
  } : { lat: 35.6762, lng: 139.6503 }; // Default to Tokyo

  const handleMarkerClick = useCallback((poi: POI) => {
    setSelectedPOI(poi);
  }, [setSelectedPOI]);

  const openInGoogleMaps = () => {
    const url = `https://www.google.com/maps/@${center.lat},${center.lng},13z`;
    window.open(url, '_blank');
  };

  // Generate Mapbox static map URL if we have valid coordinates
  const hasValidCoords = validPOIs.length > 0;
  const mapboxToken = import.meta.env.VITE_MAPBOX_PUBLIC;
  const staticMapUrl = hasValidCoords && mapboxToken
    ? `https://api.mapbox.com/styles/v1/mapbox/light-v11/static/${center.lng},${center.lat},12,0/800x600@2x?access_token=${mapboxToken}`
    : null;

  return (
    <div className="relative h-full w-full rounded-2xl overflow-hidden bg-gradient-to-br from-secondary via-muted to-secondary">
      {/* Background map image if available */}
      {staticMapUrl && (
        <div className="absolute inset-0 opacity-30">
          <img 
            src={staticMapUrl} 
            alt="Map background" 
            className="w-full h-full object-cover"
          />
        </div>
      )}
      
      {/* Map overlay with visual markers */}
      <div className="absolute inset-0 p-4">{/* Decorative grid */}
        <div className="absolute inset-0 opacity-20" style={{
          backgroundImage: 'radial-gradient(circle at 1px 1px, hsl(var(--muted-foreground)) 1px, transparent 0)',
          backgroundSize: '24px 24px'
        }} />

        {/* Header */}
        <div className="relative z-10 flex items-center justify-between mb-4">
          <div className="glass rounded-xl px-4 py-2">
            <h3 className="font-semibold text-foreground">{trip.title}</h3>
            <p className="text-xs text-muted-foreground">{allPOIs.length} locations</p>
          </div>
          <Button variant="outline" size="sm" onClick={openInGoogleMaps} className="glass">
            <ExternalLink className="h-4 w-4 mr-2" />
            Open Map
          </Button>
        </div>

        {/* POI markers arranged in a visual grid */}
        <div className="relative h-[calc(100%-80px)] flex flex-wrap gap-3 justify-center items-center content-center">
          {allPOIs.map((poi, index) => {
            const Icon = categoryIcons[poi.category];
            const isSelected = selectedPOI?.id === poi.id;

            return (
              <motion.div
                key={poi.id}
                initial={{ scale: 0, opacity: 0 }}
                animate={{ scale: 1, opacity: 1 }}
                transition={{ delay: index * 0.08, type: 'spring', bounce: 0.4 }}
                whileHover={{ scale: 1.1, y: -4 }}
                whileTap={{ scale: 0.95 }}
                onClick={() => handleMarkerClick(poi)}
                className={`relative cursor-pointer transition-all ${
                  isSelected ? 'z-20' : 'z-10'
                }`}
              >
                {/* Pulse ring for selected */}
                {isSelected && (
                  <motion.div
                    initial={{ scale: 0.8, opacity: 0 }}
                    animate={{ scale: 1.5, opacity: 0 }}
                    transition={{ repeat: Infinity, duration: 1.5 }}
                    className={`absolute inset-0 ${categoryColors[poi.category]} rounded-full`}
                  />
                )}
                
                {/* Marker */}
                <div
                  className={`relative w-14 h-14 ${categoryColors[poi.category]} rounded-2xl flex flex-col items-center justify-center shadow-lg border-2 border-card transition-all ${
                    isSelected ? 'ring-4 ring-primary/50 shadow-xl' : ''
                  }`}
                >
                  <Icon className="h-5 w-5 text-primary-foreground" />
                  <span className="text-[10px] font-medium text-primary-foreground/80 mt-0.5">
                    {index + 1}
                  </span>
                </div>

                {/* Tooltip on hover/selected */}
                {isSelected && (
                  <motion.div
                    initial={{ opacity: 0, y: 10, scale: 0.9 }}
                    animate={{ opacity: 1, y: 0, scale: 1 }}
                    className="absolute top-full left-1/2 -translate-x-1/2 mt-2 w-48 glass rounded-xl overflow-hidden shadow-xl z-30"
                  >
                    <img
                      src={poi.img}
                      alt={poi.name}
                      className="w-full h-24 object-cover"
                    />
                    <div className="p-2">
                      <div className="flex items-center gap-1 mb-1">
                        <Badge className={`${categoryColors[poi.category]} text-primary-foreground text-[10px] px-1.5 py-0`}>
                          {poi.category}
                        </Badge>
                      </div>
                      <h4 className="font-semibold text-xs text-foreground line-clamp-1">
                        {poi.name}
                      </h4>
                      <p className="text-[10px] text-muted-foreground line-clamp-2 mt-0.5">
                        {poi.vibe}
                      </p>
                    </div>
                  </motion.div>
                )}
              </motion.div>
            );
          })}
        </div>

        {/* Legend */}
        <div className="absolute bottom-4 left-4 right-4 flex flex-wrap gap-2 justify-center">
          {(['Food', 'Art', 'Nature', 'Culture', 'Shopping', 'Nightlife'] as const).map((cat) => {
            const Icon = categoryIcons[cat];
            return (
              <div key={cat} className="flex items-center gap-1 text-xs text-muted-foreground glass rounded-full px-2 py-1">
                <div className={`w-3 h-3 ${categoryColors[cat]} rounded-full flex items-center justify-center`}>
                  <Icon className="h-2 w-2 text-primary-foreground" />
                </div>
                <span>{cat}</span>
              </div>
            );
          })}
        </div>
      </div>
    </div>
  );
};
