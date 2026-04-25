import { useMemo, useState } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/components/ui/dialog';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Plus, Link, Loader2, Check, Video } from 'lucide-react';
import { processVideos } from '@/lib/api';
import { useToast } from '@/hooks/use-toast';
import { useTripContext } from '@/contexts/TripContext';

const platformPatterns = [
  { name: 'TikTok', pattern: /tiktok\.com/i, icon: '📱' },
  { name: 'Douyin', pattern: /douyin\.com/i, icon: '🎵' },
  { name: 'YouTube', pattern: /youtube\.com|youtu\.be/i, icon: '▶️' },
  { name: 'Rednote', pattern: /xiaohongshu\.com|rednote/i, icon: '📕' },
  { name: 'Instagram', pattern: /instagram\.com/i, icon: '📷' },
];

export const parseUrlsInput = (value: string): string[] => {
  const segments = value
    .split(/[\s,\n\r\t]+/g)
    .map((item) => item.trim())
    .filter(Boolean);
  const unique = Array.from(new Set(segments));
  return unique.filter((item) => /^https?:\/\//i.test(item));
};

export const AddUrlModal = () => {
  const [open, setOpen] = useState(false);
  const [rawInput, setRawInput] = useState('');
  const [isProcessing, setIsProcessing] = useState(false);
  const [isComplete, setIsComplete] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { workspaceId, ingestWorkspaceUrls, refreshWorkspaceSnapshot } = useTripContext();
  const { toast } = useToast();

  const parsedUrls = useMemo(() => parseUrlsInput(rawInput), [rawInput]);
  const detectedPlatforms = useMemo(() => {
    const names = new Set<string>();
    parsedUrls.forEach((url) => {
      platformPatterns.forEach((platform) => {
        if (platform.pattern.test(url)) names.add(platform.name);
      });
    });
    return platformPatterns.filter((platform) => names.has(platform.name));
  }, [parsedUrls]);

  const handleSubmit = async () => {
    if (parsedUrls.length === 0) return;

    setIsProcessing(true);
    setError(null);

    try {
      if (workspaceId) {
        const result = await ingestWorkspaceUrls(parsedUrls);
        await refreshWorkspaceSnapshot();
        toast({
          title: 'Workspace updated',
          description: `Imported ${result.imported} link(s)${result.failed ? `, ${result.failed} failed` : ''}.`,
        });
      } else {
        const response = await processVideos(parsedUrls);
        toast({ title: 'Success!', description: response.message });
        window.location.href = `/?trip=${response.trip_id}`;
      }

      setIsProcessing(false);
      setIsComplete(true);
      setTimeout(() => {
        setRawInput('');
        setIsComplete(false);
        setOpen(false);
      }, 900);
    } catch (err) {
      setIsProcessing(false);
      const errorMessage = err instanceof Error ? err.message : 'Failed to process videos';
      setError(errorMessage);
      toast({ variant: 'destructive', title: 'Error', description: errorMessage });
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
            Add Video Links
          </DialogTitle>
          <DialogDescription>
            Paste travel video links from TikTok, YouTube, Instagram, Douyin, or Rednote to merge them into the trip.
          </DialogDescription>
        </DialogHeader>

        <div className="space-y-4 pt-4">
          <div className="flex flex-wrap items-center justify-center gap-2">
            {platformPatterns.map((platform) => {
              const active = detectedPlatforms.some((p) => p.name === platform.name);
              return (
                <motion.div
                  key={platform.name}
                  whileHover={{ scale: 1.05 }}
                  className={`px-3 py-2 rounded-xl text-sm transition-all ${active ? 'bg-primary/10 ring-2 ring-primary' : 'bg-secondary'}`}
                >
                  {platform.icon} {platform.name}
                </motion.div>
              );
            })}
          </div>

          <div className="relative">
            <Link className="absolute left-3 top-4 h-4 w-4 text-muted-foreground" />
            <Textarea
              placeholder="Paste one or more links (newline, comma, or spaces)"
              value={rawInput}
              onChange={(e) => {
                setRawInput(e.target.value);
                setError(null);
              }}
              className="pl-10 min-h-28 rounded-xl"
              disabled={isProcessing}
            />
          </div>

          <div className="flex items-center justify-between text-xs text-muted-foreground">
            <span>{parsedUrls.length} link(s) detected</span>
            {workspaceId ? <Badge variant="secondary">Workspace ingest</Badge> : <Badge variant="outline">Trip ingest</Badge>}
          </div>

          {error && <p className="text-sm text-destructive">{error}</p>}

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
                    <p className="text-sm font-medium text-foreground">Processing {parsedUrls.length} link(s)...</p>
                    <p className="text-xs text-muted-foreground">Extracting locations and merging into the active workspace</p>
                  </div>
                </div>
              </motion.div>
            )}

            {isComplete && (
              <motion.div
                initial={{ opacity: 0, scale: 0.9 }}
                animate={{ opacity: 1, scale: 1 }}
                className="bg-category-nature/10 rounded-xl p-4 text-center"
              >
                <div className="w-12 h-12 bg-category-nature rounded-full flex items-center justify-center mx-auto mb-2">
                  <Check className="h-6 w-6 text-primary-foreground" />
                </div>
                <p className="text-sm font-medium text-foreground">Links imported successfully.</p>
              </motion.div>
            )}
          </AnimatePresence>

          {!isProcessing && !isComplete && (
            <Button onClick={handleSubmit} disabled={parsedUrls.length === 0} className="w-full gradient-bg rounded-xl">
              <Plus className="h-4 w-4 mr-2" />
              Add {parsedUrls.length > 1 ? `${parsedUrls.length} Links` : 'to Trip'}
            </Button>
          )}

          <p className="text-xs text-center text-muted-foreground">
            In workspace mode, links merge into the shared trip and refresh in place.
          </p>
        </div>
      </DialogContent>
    </Dialog>
  );
};
