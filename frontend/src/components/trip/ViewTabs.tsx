import { motion } from 'framer-motion';
import { List, LayoutGrid } from 'lucide-react';
import { useTripContext } from '@/contexts/TripContext';
import { cn } from '@/lib/utils';

const views = [
  { id: 'timeline' as const, label: 'Timeline', icon: List },
  { id: 'cards' as const, label: 'Cards', icon: LayoutGrid },
];

export const ViewTabs = () => {
  const { activeView, setActiveView } = useTripContext();

  return (
    <div className="flex items-center justify-center gap-1 p-1 bg-muted rounded-2xl w-fit mx-auto">
      {views.map((view) => (
        <motion.button
          key={view.id}
          onClick={() => setActiveView(view.id)}
          className={cn(
            "relative flex items-center gap-2 px-4 py-2 rounded-xl text-sm font-medium transition-colors",
            activeView === view.id
              ? "text-primary-foreground"
              : "text-muted-foreground hover:text-foreground"
          )}
          whileHover={{ scale: 1.02 }}
          whileTap={{ scale: 0.98 }}
        >
          {activeView === view.id && (
            <motion.div
              layoutId="activeTab"
              className="absolute inset-0 gradient-bg rounded-xl"
              transition={{ type: "spring", bounce: 0.2, duration: 0.6 }}
            />
          )}
          <view.icon className="h-4 w-4 relative z-10" />
          <span className="relative z-10 hidden sm:block">{view.label}</span>
        </motion.button>
      ))}
    </div>
  );
};
