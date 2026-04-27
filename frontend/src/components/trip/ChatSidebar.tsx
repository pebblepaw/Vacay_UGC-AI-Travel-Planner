import { useState, useRef, useEffect, useLayoutEffect } from 'react';
import { motion, AnimatePresence } from 'framer-motion';
import ReactMarkdown from 'react-markdown';
import { useTripContext } from '@/contexts/TripContext';
import { ChatMessage, ChatOption } from '@/data/mockData';
import { Sheet, SheetContent, SheetHeader, SheetTitle } from '@/components/ui/sheet';
import { Button } from '@/components/ui/button';
import { Textarea } from '@/components/ui/textarea';
import { Badge } from '@/components/ui/badge';
import { Card, CardContent } from '@/components/ui/card';
import { 
  Send, 
  Bot, 
  User, 
  Check, 
  X, 
  Clock,
  Sparkles,
  MessageCircle
} from 'lucide-react';
import { ScrollArea } from '@/components/ui/scroll-area';

const MIN_CHAT_INPUT_HEIGHT = 56;
const MAX_CHAT_INPUT_HEIGHT = 160;

const adjustTextareaHeight = (textarea: HTMLTextAreaElement | null) => {
  if (!textarea) {
    return;
  }

  textarea.style.height = 'auto';
  const nextHeight = Math.min(Math.max(textarea.scrollHeight, MIN_CHAT_INPUT_HEIGHT), MAX_CHAT_INPUT_HEIGHT);
  textarea.style.height = `${nextHeight}px`;
  textarea.style.overflowY = textarea.scrollHeight > MAX_CHAT_INPUT_HEIGHT ? 'auto' : 'hidden';
};

const MessageBubble = ({ 
  message, 
  onAction 
}: { 
  message: ChatMessage;
  onAction: (messageId: string, action: 'approve' | 'reject', optionId?: string) => void;
}) => {
  const [selectedOption, setSelectedOption] = useState<string | null>(null);

  if (message.type === 'user') {
    return (
      <motion.div
        initial={{ opacity: 0, x: 20 }}
        animate={{ opacity: 1, x: 0 }}
        className="flex justify-end mb-4"
      >
        <div className="flex items-end gap-2 min-w-0 max-w-[92%] sm:max-w-[80%]">
          <div className="gradient-bg text-primary-foreground px-4 py-2 rounded-2xl rounded-br-md break-words [overflow-wrap:anywhere] min-w-0">
            <p className="text-sm">{message.content}</p>
          </div>
          <div className="w-8 h-8 rounded-full bg-secondary flex items-center justify-center shrink-0">
            <User className="h-4 w-4 text-muted-foreground" />
          </div>
        </div>
      </motion.div>
    );
  }

  if (message.type === 'interrupt') {
    const isOpenUrlInterrupt = message.interrupt_type === 'open_url' && Boolean(message.content);
    return (
      <motion.div
        initial={{ opacity: 0, y: 20 }}
        animate={{ opacity: 1, y: 0 }}
        className="mb-4"
      >
        <div className="flex items-end gap-2">
          <div className="w-8 h-8 rounded-full gradient-bg flex items-center justify-center shrink-0">
            <Bot className="h-4 w-4 text-primary-foreground" />
          </div>
          <div className="flex-1">
            <Card className="overflow-hidden border-accent/30">
              <CardContent className="p-4">
                {/* Status indicator */}
                {!isOpenUrlInterrupt && (
                  <div className="flex items-center gap-2 mb-3">
                    {message.status === 'pending' && (
                      <Badge variant="secondary" className="gap-1 text-xs">
                        <Clock className="h-3 w-3" />
                        Waiting for input
                      </Badge>
                    )}
                    {message.status === 'approved' && (
                      <Badge className="bg-category-nature text-primary-foreground gap-1 text-xs">
                        <Check className="h-3 w-3" />
                        Approved
                      </Badge>
                    )}
                    {message.status === 'rejected' && (
                      <Badge variant="destructive" className="gap-1 text-xs">
                        <X className="h-3 w-3" />
                        Rejected
                      </Badge>
                    )}
                  </div>
                )}

                {isOpenUrlInterrupt ? (
                  <div className="space-y-3">
                    <Badge variant="secondary" className="gap-1 text-xs">
                      <Sparkles className="h-3 w-3" />
                      Booking handoff ready
                    </Badge>
                    <p className="text-sm text-foreground">
                      The provider checkout page is ready. Open it from here whenever you want to continue.
                    </p>
                    <a
                      href={message.content}
                      target="_blank"
                      rel="noopener noreferrer"
                      className="inline-flex items-center rounded-lg bg-primary px-3 py-2 text-sm font-medium text-primary-foreground hover:opacity-90"
                    >
                      Open booking handoff
                    </a>
                    <p className="text-xs text-muted-foreground break-all [overflow-wrap:anywhere]">
                      {message.content}
                    </p>
                  </div>
                ) : (
                  <p className="text-sm text-foreground mb-4">{message.content}</p>
                )}

                {/* Options */}
                {message.options && message.status === 'pending' && !isOpenUrlInterrupt && (
                  <div className="space-y-2 mb-4">
                    {message.options.map((option: ChatOption) => (
                      <motion.div
                        key={option.id}
                        whileHover={{ scale: 1.02 }}
                        whileTap={{ scale: 0.98 }}
                        onClick={() => setSelectedOption(option.id)}
                        className={`p-3 rounded-xl border cursor-pointer transition-all ${
                          selectedOption === option.id
                            ? 'border-primary bg-primary/5'
                            : 'border-border hover:border-primary/50'
                        }`}
                      >
                        <div className="flex items-center justify-between mb-1">
                          <span className="font-medium text-sm text-foreground">
                            {option.name}
                          </span>
                          <span className="text-sm font-semibold text-primary">
                            ${option.price}
                          </span>
                        </div>
                        <p className="text-xs text-muted-foreground">
                          {option.description}
                        </p>
                      </motion.div>
                    ))}
                  </div>
                )}

                {/* Action buttons */}
                {message.status === 'pending' && !isOpenUrlInterrupt && (
                  <div className="flex gap-2">
                    <Button
                      size="sm"
                      onClick={() => onAction(message.id, 'approve', selectedOption || undefined)}
                      disabled={!selectedOption && !!message.options}
                      className="flex-1 gradient-bg"
                    >
                      <Check className="h-4 w-4 mr-1" />
                      Approve
                    </Button>
                    <Button
                      size="sm"
                      variant="outline"
                      onClick={() => onAction(message.id, 'reject')}
                    >
                      <X className="h-4 w-4 mr-1" />
                      Reject
                    </Button>
                  </div>
                )}
              </CardContent>
            </Card>
          </div>
        </div>
      </motion.div>
    );
  }

  // Agent message
  return (
    <motion.div
      initial={{ opacity: 0, x: -20 }}
      animate={{ opacity: 1, x: 0 }}
      className="flex items-start gap-2 mb-4"
    >
      <div className="w-8 h-8 rounded-full gradient-bg flex items-center justify-center shrink-0 mt-1">
        <Bot className="h-4 w-4 text-primary-foreground" />
      </div>
      <div className="bg-secondary px-4 py-2 rounded-2xl rounded-bl-md min-w-0 max-w-[92%] sm:max-w-[80%] break-words [overflow-wrap:anywhere] prose prose-sm prose-invert dark:prose-invert
        [&_p]:text-sm [&_p]:text-foreground [&_p]:my-1
        [&_strong]:text-foreground [&_strong]:font-semibold
        [&_ul]:my-1 [&_ul]:pl-4 [&_ul]:list-disc
        [&_ol]:my-1 [&_ol]:pl-4 [&_ol]:list-decimal
        [&_li]:text-sm [&_li]:text-foreground [&_li]:my-0.5
        [&_h1]:text-base [&_h1]:font-bold [&_h1]:my-2 [&_h1]:text-foreground
        [&_h2]:text-sm [&_h2]:font-bold [&_h2]:my-2 [&_h2]:text-foreground
        [&_h3]:text-sm [&_h3]:font-semibold [&_h3]:my-1.5 [&_h3]:text-foreground
        [&_hr]:my-2 [&_hr]:border-border
        [&_a]:text-primary [&_a]:underline
      ">
        <ReactMarkdown>{message.content}</ReactMarkdown>
      </div>
    </motion.div>
  );
};

export const ChatSidebar = () => {
  const { isChatOpen, setIsChatOpen, chatMessages, sendUserMessage, handleInterruptAction } = useTripContext();
  const [inputValue, setInputValue] = useState('');
  const scrollRef = useRef<HTMLDivElement>(null);
  const textareaRef = useRef<HTMLTextAreaElement>(null);

  // Auto-scroll to bottom on new messages
  useEffect(() => {
    if (scrollRef.current) {
      scrollRef.current.scrollTop = scrollRef.current.scrollHeight;
    }
  }, [chatMessages]);

  useLayoutEffect(() => {
    adjustTextareaHeight(textareaRef.current);
  }, [inputValue, isChatOpen]);

  const handleSend = () => {
    if (inputValue.trim()) {
      sendUserMessage(inputValue.trim());
      setInputValue('');
    }
  };

  const handleKeyPress = (e: React.KeyboardEvent) => {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault();
      handleSend();
    }
  };

  return (
    <>
      {/* Floating Chat Button */}
      <AnimatePresence>
        {!isChatOpen && (
          <motion.button
            initial={{ scale: 0 }}
            animate={{ scale: 1 }}
            exit={{ scale: 0 }}
            whileHover={{ scale: 1.1 }}
            whileTap={{ scale: 0.9 }}
            onClick={() => setIsChatOpen(true)}
            className="fixed bottom-6 right-6 z-50 w-14 h-14 gradient-bg rounded-full flex items-center justify-center shadow-lg shadow-primary/30"
          >
            <MessageCircle className="h-6 w-6 text-primary-foreground" />
            
            {/* Notification dot */}
            <div className="absolute -top-1 -right-1 w-5 h-5 bg-category-food rounded-full flex items-center justify-center">
              <span className="text-xs font-bold text-primary-foreground">1</span>
            </div>
          </motion.button>
        )}
      </AnimatePresence>

      {/* Chat Sheet */}
      <Sheet open={isChatOpen} onOpenChange={setIsChatOpen}>
        <SheetContent side="right" className="w-[100vw] max-w-full sm:max-w-md p-0 flex flex-col overflow-hidden">
          <SheetHeader className="p-4 border-b border-border">
            <div className="flex items-center gap-3">
              <div className="w-10 h-10 gradient-bg rounded-xl flex items-center justify-center">
                <Sparkles className="h-5 w-5 text-primary-foreground" />
              </div>
              <div>
                <SheetTitle className="text-left">Trip Assistant</SheetTitle>
                <p className="text-xs text-muted-foreground text-left">
                  Powered by AI • Always here to help
                </p>
              </div>
            </div>
          </SheetHeader>

          {/* Messages */}
          <ScrollArea className="flex-1 p-4" ref={scrollRef}>
            <div className="space-y-1">
              {chatMessages.map((message) => (
                <MessageBubble 
                  key={message.id} 
                  message={message}
                  onAction={handleInterruptAction}
                />
              ))}
            </div>
          </ScrollArea>

          {/* Input */}
          <div className="p-4 border-t border-border">
            <div className="flex items-end gap-2">
              <Textarea
                ref={textareaRef}
                placeholder="Ask anything about your trip..."
                value={inputValue}
                onChange={(e) => setInputValue(e.target.value)}
                onKeyDown={handleKeyPress}
                rows={1}
                className="flex-1 min-h-[56px] max-h-[160px] resize-none overflow-y-auto rounded-xl"
              />
              <Button
                size="icon"
                onClick={handleSend}
                disabled={!inputValue.trim()}
                aria-label="Send message"
                className="gradient-bg rounded-xl"
              >
                <Send className="h-4 w-4" />
              </Button>
            </div>
            <div className="flex gap-2 mt-2">
              <Button
                variant="secondary"
                size="sm"
                className="text-xs rounded-full"
                onClick={() => sendUserMessage("Can you find a cheaper hotel?")}
              >
                💰 Cheaper hotel
              </Button>
              <Button
                variant="secondary"
                size="sm"
                className="text-xs rounded-full"
                onClick={() => sendUserMessage("Add a coffee shop near TeamLab")}
              >
                ☕ Add coffee
              </Button>
            </div>
          </div>
        </SheetContent>
      </Sheet>
    </>
  );
};
