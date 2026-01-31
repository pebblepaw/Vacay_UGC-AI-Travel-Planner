import { useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import { 
  Dialog, 
  DialogContent, 
  DialogHeader, 
  DialogTitle, 
  DialogTrigger 
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Input } from '@/components/ui/input';
import { Badge } from '@/components/ui/badge';
import { 
  Plus, 
  Link, 
  Loader2,
  Check,
  Video,
  AlertCircle
} from 'lucide-react';
import { processVideos } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';

const platformPatterns = [
  { name: 'TikTok', pattern: /tiktok\.com/, icon: '📱', color: 'bg-foreground' },
  { name: 'Douyin', pattern: /douyin\.com/, icon: '🎵', color: 'bg-foreground' },
  { name: 'YouTube', pattern: /youtube\.com|youtu\.be/, icon: '▶️', color: 'bg-destructive' },
  { name: 'Rednote', pattern: /xiaohongshu\.com/, icon: '📕', color: 'bg-destructive' },
];

export const AddUrlModal = () => {
  const [open, setOpen] = useState(false);
  const [url, setUrl] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [detectedPlatform, setDetectedPlatform] = useState<typeof platformPatterns[0] | null>(null);
  const { toast } = useToast();

  const handleUrlChange = (value: string) => {
    setUrl(value);
    setError(null);
    
    // Detect platform
    const platform = platformPatterns.find(p => p.pattern.test(value));
    setDetectedPlatform(platform || null);
  };

  const handleSubmit = async () => {
    if (!url.trim()) return;

    setIsProcessing(true);
    setError(null);
    
    try {
      // Call backend API
      const response = await processVideos([url]);
      
      setIsProcessing(false);
      setIsComplete(true);
      
      toast({
        title: "Success!",
        description: response.message,
      });
      
      // Reset after showing success
      setTimeout(() => {
        setUrl('');
        setIsComplete(false);
        setDetectedPlatform(null);
        setOpen(false);
        
        // Reload page to show new trip (for now)
        window.location.href = `/trip/${response.trip_id}`;
      }, 1500);
    } catch (err) {
      setIsProcessing(false);
      const errorMessage = err instanceof Error ? err.message : 'Failed to process video';
      setError(errorMessage);
      
      toast({
        variant: "destructive",
        title: "Error",
        description: errorMessage,
      });
    }
  };

  return (
    <Dialog open={open} onOpenChange={setOpen}>
      <DialogTrigger asChild>
        <motion.button
          whileHover={{ scale: 1.1 }}
          whileTap={{ scale: 0.9 }}
          className="fixed bottom-6 left-6 z-50 w-14 h-14 gradient-bg rounded-full flex items-center justify-center shadow-lg shadow-primary/30"
        >
          <Plus className="h-6 w-6 text-primary-foreground" />
        </motion.button>
      </DialogTrigger>

      <DialogContent className="sm:max-w-md">
        <DialogHeader>
          <DialogTitle className="flex items-center gap-2">
            <Video className="h-5 w-5 text-primary" />
            Add Video to Trip
          </DialogTitle>
        </DialogHeader>

        <div className="space-y-4 pt-4">
          {/* Platform icons */}
          <div className="flex items-center justify-center gap-4">
            {platformPatterns.map((platform) => (
              <motion.div
                key={platform.name}
                whileHover={{ scale: 1.1 }}
                className={`w-12 h-12 rounded-xl flex items-center justify-center text-xl transition-all ${
                  detectedPlatform?.name === platform.name
                    ? 'bg-primary/10 ring-2 ring-primary'
                    : 'bg-secondary'
                }`}
              >
                {platform.icon}
              </motion.div>
            ))}
          </div>

          {/* URL Input */}
          <div className="relative">
            <Link className="absolute left-3 top-1/2 -translate-y-1/2 h-4 w-4 text-muted-foreground" />
            <Input
              placeholder="Paste TikTok, Douyin, YouTube, or Rednote URL..."
              value={url}
              onChange={(e) => handleUrlChange(e.target.value)}
              className="pl-10 rounded-xl"
              disabled={isProcessing}
            />
            {detectedPlatform && !isProcessing && (
              <Badge className="absolute right-2 top-1/2 -translate-y-1/2 text-xs">
                {detectedPlatform.icon} {detectedPlatform.name}
              </Badge>
            )}
          </div>

          {/* Processing state */}
          <AnimatePresence mode="wait">
            {isProcessing && (
              <motion.div
                initial={{ opacity: 0, height: 0 }}
                animate={{ opacity: 1, height: 'auto' }}
                exit={{ opacity: 0, height: 0 }}
                className="bg-secondary rounded-xl p-4"
              >
                <div className="flex items-center gap-3">
                  <Loader2 className="h-5 w-5 animate-spin text-primary" />
                  <div className="flex-1">
                    <p className="text-sm font-medium text-foreground">
                      Extracting video content...
                    </p>
                    <p className="text-xs text-muted-foreground">
                      Analyzing locations, vibes, and recommendations
                    </p>
                  </div>
                </div>
                
                {/* Progress bar */}
                <div className="mt-3 h-1.5 bg-muted rounded-full overflow-hidden">
                  <motion.div
                    initial={{ width: '0%' }}
                    animate={{ width: '100%' }}
                    transition={{ duration: 2 }}
                    className="h-full gradient-bg"
                  />
                </div>
              </motion.div>
            )}

            {isComplete && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-category-nature/10 rounded-xl p-4 text-center"
              >
                <motion.div
                  initial={{ scale: 0 }}
                  animate={{ scale: 1 }}
                  transition={{ type: 'spring', bounce: 0.5 }}
                  className="w-12 h-12 bg-category-nature rounded-full flex items-center justify-center mx-auto mb-2"
                >
                  <Check className="h-6 w-6 text-primary-foreground" />
                </motion.div>
                <p className="text-sm font-medium text-foreground">
                  Video added to your trip!
                </p>
              </motion.div>
            )}
          </AnimatePresence>

          {/* Submit button */}
          {!isProcessing && !isComplete && (
            <Button
              onClick={handleSubmit}
              disabled={!url.trim()}
              className="w-full gradient-bg rounded-xl"
            >
              <Plus className="h-4 w-4 mr-2" />
              Add to Trip
            </Button>
          )}

          {/* Helper text */}
          <p className="text-xs text-center text-muted-foreground">
            Paste any travel video URL and we'll extract the locations automatically
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
