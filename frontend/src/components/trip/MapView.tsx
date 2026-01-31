import { useEffect, useRef, useCallback } from 'react';
import { motion } from 'framer-motion';
import mapboxgl from 'mapbox-gl';
import 'mapbox-gl/dist/mapbox-gl.css';
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
  Food: '#f97316',      // orange-500
  Art: '#a855f7',       // purple-500
  Nature: '#22c55e',    // green-500
  Culture: '#f59e0b',   // amber-500
  Shopping: '#ec4899',  // pink-500
  Nightlife: '#6366f1', // indigo-500
};

const categoryBgColors: Record<POI['category'], string> = {
  Food: 'bg-category-food',
  Art: 'bg-category-art',
  Nature: 'bg-category-nature',
  Culture: 'bg-category-culture',
  Shopping: 'bg-category-shopping',
  Nightlife: 'bg-category-nightlife',
};

export const MapView = () => {
  const { trip, selectedPOI, setSelectedPOI } = useTripContext();
  const mapContainerRef = useRef<HTMLDivElement>(null);
  const mapRef = useRef<mapboxgl.Map | null>(null);
  const markersRef = useRef<mapboxgl.Marker[]>([]);

  const allPOIs = trip.days.flatMap((day) => day.pois);
  const validPOIs = allPOIs.filter(poi => poi.coords[0] !== 0 && poi.coords[1] !== 0);

  // Calculate center from POI coordinates
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

  // Initialize map
  useEffect(() => {
    if (!mapContainerRef.current) return;
    
    const mapboxToken = import.meta.env.VITE_MAPBOX_PUBLIC;
    if (!mapboxToken) {
      console.error('Mapbox token not found');
      return;
    }

    mapboxgl.accessToken = mapboxToken;

    const map = new mapboxgl.Map({
      container: mapContainerRef.current,
      style: 'mapbox://styles/mapbox/light-v11',
      center: [center.lng, center.lat],
      zoom: 12,
    });

    // Add navigation controls
    map.addControl(new mapboxgl.NavigationControl(), 'top-right');

    mapRef.current = map;

    // Cleanup
    return () => {
      markersRef.current.forEach(marker => marker.remove());
      markersRef.current = [];
      map.remove();
    };
  }, []); // Only run once on mount

  // Update map center when trip changes
  useEffect(() => {
    if (mapRef.current && validPOIs.length > 0) {
      // Fit bounds to show all POIs
      const bounds = new mapboxgl.LngLatBounds();
      validPOIs.forEach(poi => {
        bounds.extend([poi.coords[0], poi.coords[1]]);
      });
      
      mapRef.current.fitBounds(bounds, {
        padding: { top: 50, bottom: 50, left: 50, right: 50 },
        maxZoom: 14,
      });
    }
  }, [validPOIs]);

  // Add markers
  useEffect(() => {
    if (!mapRef.current) return;

    // Clear existing markers
    markersRef.current.forEach(marker => marker.remove());
    markersRef.current = [];

    // Add new markers for each POI
    validPOIs.forEach((poi, index) => {
      // Create custom marker element
      const el = document.createElement('div');
      el.className = 'mapbox-marker';
      el.style.cssText = `
        width: 36px;
        height: 36px;
        background-color: ${categoryColors[poi.category]};
        border: 3px solid white;
        border-radius: 50%;
        display: flex;
        align-items: center;
        justify-content: center;
        cursor: pointer;
        box-shadow: 0 4px 12px rgba(0,0,0,0.3);
        transition: transform 0.2s ease;
        font-size: 12px;
        font-weight: bold;
        color: white;
      `;
      el.innerHTML = `${index + 1}`;
      
      // Add hover effect
      el.addEventListener('mouseenter', () => {
        el.style.transform = 'scale(1.2)';
      });
      el.addEventListener('mouseleave', () => {
        el.style.transform = selectedPOI?.id === poi.id ? 'scale(1.3)' : 'scale(1)';
      });

      // Create popup
      const popup = new mapboxgl.Popup({
        offset: 25,
        closeButton: false,
        closeOnClick: false,
        maxWidth: '200px',
      }).setHTML(`
        <div style="padding: 8px;">
          <img src="${poi.img}" alt="${poi.name}" style="width: 100%; height: 80px; object-fit: cover; border-radius: 8px; margin-bottom: 8px;" onerror="this.src='https://placehold.co/200x80/1a1a2e/eaeaea?text=${encodeURIComponent(poi.name.slice(0, 15))}'"/>
          <div style="font-weight: 600; font-size: 14px; margin-bottom: 4px;">${poi.name}</div>
          <div style="font-size: 12px; color: #666;">${poi.category} • ${poi.time_slot || 'Flexible'}</div>
        </div>
      `);

      // Create marker
      const marker = new mapboxgl.Marker({ element: el })
        .setLngLat([poi.coords[0], poi.coords[1]])
        .setPopup(popup)
        .addTo(mapRef.current!);

      // Handle click
      el.addEventListener('click', () => {
        handleMarkerClick(poi);
      });

      // Show popup on hover
      el.addEventListener('mouseenter', () => {
        marker.togglePopup();
      });
      el.addEventListener('mouseleave', () => {
        marker.togglePopup();
      });

      markersRef.current.push(marker);
    });
  }, [validPOIs, handleMarkerClick]);

  // Highlight selected marker
  useEffect(() => {
    markersRef.current.forEach((marker, index) => {
      const el = marker.getElement();
      const poi = validPOIs[index];
      if (poi && selectedPOI?.id === poi.id) {
        el.style.transform = 'scale(1.3)';
        el.style.zIndex = '100';
        el.style.boxShadow = '0 0 20px rgba(99, 102, 241, 0.6)';
      } else {
        el.style.transform = 'scale(1)';
        el.style.zIndex = '1';
        el.style.boxShadow = '0 4px 12px rgba(0,0,0,0.3)';
      }
    });
  }, [selectedPOI, validPOIs]);

  const hasValidCoords = validPOIs.length > 0;

  return (
    <div className="relative h-full w-full rounded-2xl overflow-hidden bg-gradient-to-br from-secondary via-muted to-secondary">
      {/* Map container */}
      {hasValidCoords ? (
        <div ref={mapContainerRef} className="absolute inset-0" />
      ) : (
        <div className="absolute inset-0 flex items-center justify-center">
          <div className="text-center p-8">
            <MapPin className="h-16 w-16 mx-auto mb-4 text-muted-foreground opacity-50" />
            <h3 className="text-lg font-semibold text-muted-foreground">No locations yet</h3>
            <p className="text-sm text-muted-foreground mt-2">
              Add a TikTok video to see locations on the map
            </p>
          </div>
        </div>
      )}

      {/* Header overlay */}
      <div className="absolute top-4 left-4 right-4 z-10 flex items-center justify-between pointer-events-none">
        <div className="glass rounded-xl px-4 py-2 pointer-events-auto">
          <h3 className="font-semibold text-foreground">{trip.title}</h3>
          <p className="text-xs text-muted-foreground">{allPOIs.length} locations</p>
        </div>
        <Button variant="outline" size="sm" onClick={openInGoogleMaps} className="glass pointer-events-auto">
          <ExternalLink className="h-4 w-4 mr-2" />
          Open Map
        </Button>
      </div>

      {/* Legend */}
      <div className="absolute bottom-4 left-4 right-4 flex flex-wrap gap-2 justify-center z-10 pointer-events-none">
        {(['Food', 'Art', 'Nature', 'Culture', 'Shopping', 'Nightlife'] as const).map((cat) => {
          const Icon = categoryIcons[cat];
          return (
            <div key={cat} className="flex items-center gap-1 text-xs text-muted-foreground glass rounded-full px-2 py-1">
              <div 
                className={`w-3 h-3 rounded-full flex items-center justify-center`}
                style={{ backgroundColor: categoryColors[cat] }}
              >
                <Icon className="h-2 w-2 text-white" />
              </div>
              <span>{cat}</span>
            </div>
          );
        })}
      </div>

      {/* Selected POI info panel */}
      {selectedPOI && (
        <motion.div
          initial={{ opacity: 0, y: 20 }}
          animate={{ opacity: 1, y: 0 }}
          exit={{ opacity: 0, y: 20 }}
          className="absolute bottom-20 left-4 right-4 z-20 glass rounded-xl overflow-hidden shadow-xl max-w-sm mx-auto"
        >
          <div className="flex">
            <img
              src={selectedPOI.img}
              alt={selectedPOI.name}
              className="w-24 h-24 object-cover flex-shrink-0"
              onError={(e) => {
                e.currentTarget.src = `https://placehold.co/96x96/1a1a2e/eaeaea?text=${encodeURIComponent(selectedPOI.name.slice(0, 10))}`;
              }}
            />
            <div className="p-3 flex-1">
              <div className="flex items-center gap-2 mb-1">
                <Badge className={`${categoryBgColors[selectedPOI.category]} text-primary-foreground text-xs`}>
                  {selectedPOI.category}
                </Badge>
              </div>
              <h4 className="font-semibold text-sm text-foreground line-clamp-1">
                {selectedPOI.name}
              </h4>
              <p className="text-xs text-muted-foreground line-clamp-2 mt-1">
                {selectedPOI.vibe}
              </p>
            </div>
          </div>
        </motion.div>
      )}
    </div>
  );
};
