import { motion } from 'framer-motion';
import { Share2, Settings, Video, Calendar, MapPin } from 'lucide-react';
import { Button } from '@/components/ui/button';
import { Badge } from '@/components/ui/badge';
import { useTripContext } from '@/contexts/TripContext';
import { getPlatformIcon } from '@/data/mockData';
import { useToast } from '@/hooks/use-toast';

export const TripHeader = () => {
  const { trip, workspaceId, createShareLink } = useTripContext();
  const { toast } = useToast();

  const onShare = async () => {
    if (!workspaceId) {
      await navigator.clipboard.writeText(window.location.href);
      toast({ title: 'Link copied', description: 'Trip link copied to clipboard.' });
      return;
    }
    const url = await createShareLink();
    if (url) {
      await navigator.clipboard.writeText(url);
      toast({ title: 'Workspace link copied', description: 'Signed workspace handoff link copied.' });
    } else {
      toast({ variant: 'destructive', title: 'Share failed', description: 'Could not generate workspace share link.' });
    }
  };

  return (
    <motion.header
      initial={{ opacity: 0, y: -20 }}
      animate={{ opacity: 1, y: 0 }}
      className="glass sticky top-0 z-40 border-b border-border/50"
    >
      <div className="flex items-center justify-between px-4 py-3 md:px-6">
        <div className="flex items-center gap-4">
          <motion.div whileHover={{ scale: 1.05 }} className="flex items-center gap-2">
            <div className="gradient-bg h-8 w-8 rounded-xl flex items-center justify-center">
              <MapPin className="h-4 w-4 text-primary-foreground" />
            </div>
            <span className="text-xl font-bold gradient-text hidden sm:block">VACAY</span>
          </motion.div>

          <div className="h-6 w-px bg-border hidden sm:block" />

          <div className="flex flex-col">
            <h1 className="text-lg font-semibold text-foreground md:text-xl">{trip.title}</h1>
            <div className="flex items-center gap-2 text-sm text-muted-foreground">
              <Badge variant="secondary" className="gap-1 text-xs">
                <Calendar className="h-3 w-3" />
                {trip.days.length} Days
              </Badge>
              <Badge variant="secondary" className="gap-1 text-xs">
                <Video className="h-3 w-3" />
                {trip.source_videos.length} videos
              </Badge>
              {workspaceId && (
                <Badge variant="outline" className="gap-1 text-[10px]">
                  Workspace
                </Badge>
              )}
            </div>
          </div>
        </div>

        <div className="flex items-center gap-2">
          <div className="hidden lg:flex items-center gap-1">
            {trip.source_videos.slice(0, 3).map((video, i) => (
              <motion.div
                key={i}
                whileHover={{ scale: 1.1 }}
                className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center text-sm cursor-pointer"
                title={video.title}
              >
                {getPlatformIcon(video.platform)}
              </motion.div>
            ))}
            {trip.source_videos.length > 3 && (
              <span className="text-sm text-muted-foreground">+{trip.source_videos.length - 3}</span>
            )}
          </div>

          <Button variant="ghost" size="icon" className="rounded-full" onClick={onShare}>
            <Share2 className="h-4 w-4" />
          </Button>
          <Button variant="ghost" size="icon" className="rounded-full">
            <Settings className="h-4 w-4" />
          </Button>
        </div>
      </div>
    </motion.header>
  );
};
