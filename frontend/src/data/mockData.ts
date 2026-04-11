// Mock data for VACAY - AI Travel Itinerary Planner

export interface SourceVideo {
  platform: 'tiktok' | 'douyin' | 'youtube' | 'rednote';
  url: string;
  title: string;
}

export interface POI {
  id: string;
  name: string;
  category: 'Food' | 'Art' | 'Nature' | 'Culture' | 'Shopping' | 'Nightlife';
  coords: [number, number]; // [lng, lat]
  img: string;
  time_slot: string;
  vibe: string;
  travel_time?: string;
}

export interface Day {
  day_number: number;
  date: string;
  pois: POI[];
}

export interface Accommodation {
  name: string;
  price_per_night: number;
  status: string;
  img: string;
  coords: [number, number];
}

export interface Trip {
  trip_id: string;
  title: string;
  source_videos: SourceVideo[];
  days: Day[];
  accommodation: Accommodation;
}

export interface ChatOption {
  id: string;
  name: string;
  price: number;
  description: string;
}

export interface ChatMessage {
  id: string;
  type: 'user' | 'agent' | 'interrupt';
  content: string;
  timestamp: Date;
  interrupt_type?: 'hotel_selection' | 'poi_selection' | 'confirmation' | 'open_url';
  options?: ChatOption[];
  status?: 'pending' | 'approved' | 'rejected';
}

export const sampleTrip: Trip = {
  trip_id: "tokyo-vibe-001",
  title: "Hidden Gems of Tokyo",
  source_videos: [
    { platform: 'tiktok', url: 'https://tiktok.com/@user/video1', title: 'Best ramen in Shinjuku 🍜' },
    { platform: 'douyin', url: 'https://douyin.com/video2', title: '新宿の隠れ家ラーメン' },
    { platform: 'youtube', url: 'https://youtube.com/shorts/abc123', title: 'TeamLab is INSANE' },
    { platform: 'rednote', url: 'https://xiaohongshu.com/note3', title: '原宿购物攻略' },
    { platform: 'tiktok', url: 'https://tiktok.com/@user/video4', title: 'Tokyo nightlife guide' },
  ],
  days: [
    {
      day_number: 1,
      date: "2024-04-15",
      pois: [
        {
          id: "poi_1",
          name: "TeamLab Borderless",
          category: "Art",
          coords: [139.7834, 35.6267],
          img: "https://images.unsplash.com/photo-1549887534-1541e9326642?w=600&h=400&fit=crop",
          time_slot: "10:00 - 13:00",
          vibe: "Immersive digital art featured in 5 of your saved videos. Mind-bending infinity rooms and flowing water projections.",
          travel_time: "🚃 25 min train"
        },
        {
          id: "poi_2",
          name: "Shinjuku Gyoen Ramen",
          category: "Food",
          coords: [139.7100, 35.6850],
          img: "https://images.unsplash.com/photo-1557872943-16a5ac26437e?w=600&h=400&fit=crop",
          time_slot: "13:30 - 14:30",
          vibe: "The 'secret ramen' spot from the Douyin clip. Rich tonkotsu broth with homemade noodles.",
          travel_time: "🚶 15 min walk"
        },
        {
          id: "poi_3",
          name: "Shinjuku Gyoen Garden",
          category: "Nature",
          coords: [139.7100, 35.6852],
          img: "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&h=400&fit=crop",
          time_slot: "15:00 - 17:00",
          vibe: "Serene Japanese garden perfect for afternoon strolls. Cherry blossoms in spring!",
          travel_time: "🚕 10 min taxi"
        }
      ]
    },
    {
      day_number: 2,
      date: "2024-04-16",
      pois: [
        {
          id: "poi_4",
          name: "Harajuku Takeshita Street",
          category: "Shopping",
          coords: [139.7028, 35.6716],
          img: "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600&h=400&fit=crop",
          time_slot: "10:00 - 12:00",
          vibe: "Kawaii culture central! Crepe shops, vintage finds, and street fashion galore.",
          travel_time: "🚃 20 min train"
        },
        {
          id: "poi_5",
          name: "Meiji Shrine",
          category: "Culture",
          coords: [139.6993, 35.6764],
          img: "https://images.unsplash.com/photo-1583766395091-2eb9994ed094?w=600&h=400&fit=crop",
          time_slot: "12:30 - 14:00",
          vibe: "Peaceful forest oasis in the heart of Tokyo. Traditional Shinto shrine experience.",
          travel_time: "🚶 8 min walk"
        },
        {
          id: "poi_6",
          name: "Shibuya Crossing",
          category: "Culture",
          coords: [139.7016, 35.6595],
          img: "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600&h=400&fit=crop",
          time_slot: "14:30 - 15:30",
          vibe: "The world's busiest intersection! Watch from Starbucks for the best view.",
          travel_time: "🚃 15 min train"
        },
        {
          id: "poi_7",
          name: "Golden Gai",
          category: "Nightlife",
          coords: [139.7050, 35.6938],
          img: "https://images.unsplash.com/photo-1554797589-7241bb691973?w=600&h=400&fit=crop",
          time_slot: "19:00 - 23:00",
          vibe: "Tiny bars, big vibes. Over 200 micro-bars in narrow alleys. The TikTok nightlife spot!",
        }
      ]
    },
    {
      day_number: 3,
      date: "2024-04-17",
      pois: [
        {
          id: "poi_8",
          name: "Tsukiji Outer Market",
          category: "Food",
          coords: [139.7706, 35.6654],
          img: "https://images.unsplash.com/photo-1553621042-f6e147245754?w=600&h=400&fit=crop",
          time_slot: "07:00 - 09:00",
          vibe: "Fresh sushi breakfast! The early bird catches the best tuna.",
          travel_time: "🚃 30 min train"
        },
        {
          id: "poi_9",
          name: "Senso-ji Temple",
          category: "Culture",
          coords: [139.7966, 35.7148],
          img: "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600&h=400&fit=crop",
          time_slot: "10:00 - 12:00",
          vibe: "Tokyo's oldest temple with iconic red lantern gate. Don't miss the shopping street!",
          travel_time: "🚶 10 min walk"
        },
        {
          id: "poi_10",
          name: "Akihabara Electric Town",
          category: "Shopping",
          coords: [139.7731, 35.7023],
          img: "https://images.unsplash.com/photo-1528164344705-47542687000d?w=600&h=400&fit=crop",
          time_slot: "14:00 - 17:00",
          vibe: "Anime paradise! Arcades, maid cafes, and retro game shops everywhere.",
        }
      ]
    }
  ],
  accommodation: {
    name: "Shinjuku Airbnb High-rise",
    price_per_night: 145,
    status: "Found via Playwright - Best Match",
    img: "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
    coords: [139.6917, 35.6895]
  }
};

export const initialChatMessages: ChatMessage[] = [
  {
    id: "msg_1",
    type: "agent",
    content: "Hey! 👋 I've created your Tokyo itinerary based on 5 videos you saved. I found some amazing hidden gems!",
    timestamp: new Date(Date.now() - 3600000),
  },
  {
    id: "msg_2",
    type: "agent",
    content: "I noticed you saved a lot of food content, so I made sure to include the best ramen and sushi spots.",
    timestamp: new Date(Date.now() - 3500000),
  },
  {
    id: "msg_3",
    type: "interrupt",
    content: "I found 3 Airbnbs near your ramen spot. Which one works best for you?",
    timestamp: new Date(Date.now() - 3400000),
    interrupt_type: "hotel_selection",
    status: "approved",
    options: [
      { id: "opt_1", name: "Cozy Studio Shinjuku", price: 120, description: "5 min walk to station, compact but modern" },
      { id: "opt_2", name: "High-rise with View", price: 145, description: "Amazing city views, 10 min to ramen spot" },
      { id: "opt_3", name: "Traditional Ryokan Style", price: 180, description: "Tatami floors, onsen bath, authentic experience" },
    ]
  },
  {
    id: "msg_4",
    type: "user",
    content: "I'll take the high-rise with the view! 🏙️",
    timestamp: new Date(Date.now() - 3300000),
  },
  {
    id: "msg_5",
    type: "agent",
    content: "Great choice! I've locked in the Shinjuku High-rise for you. The view is incredible at night! ✨",
    timestamp: new Date(Date.now() - 3200000),
  },
];

export const mockChatResponses: Record<string, ChatMessage> = {
  "cheaper hotel": {
    id: "response_cheaper",
    type: "interrupt",
    content: "Found some budget-friendly options nearby! 💰",
    timestamp: new Date(),
    interrupt_type: "hotel_selection",
    status: "pending",
    options: [
      { id: "budget_1", name: "Capsule Hotel Shinjuku", price: 45, description: "Unique experience, very compact" },
      { id: "budget_2", name: "Hostel Share Room", price: 35, description: "Social atmosphere, shared facilities" },
      { id: "budget_3", name: "Business Hotel Basic", price: 75, description: "Simple but comfortable, near station" },
    ]
  },
  "sushi": {
    id: "response_sushi",
    type: "interrupt",
    content: "I found an amazing sushi spot to replace the ramen! 🍣",
    timestamp: new Date(),
    interrupt_type: "poi_selection",
    status: "pending",
    options: [
      { id: "sushi_1", name: "Sushi Dai", price: 80, description: "Famous Tsukiji sushi, worth the wait" },
      { id: "sushi_2", name: "Midori Sushi", price: 45, description: "Great value conveyor belt sushi" },
      { id: "sushi_3", name: "Sukiyabashi Jiro", price: 300, description: "The legendary omakase experience" },
    ]
  },
  "coffee": {
    id: "response_coffee",
    type: "agent",
    content: "Added 'Blue Bottle Coffee Odaiba' near TeamLab! ☕ Perfect for a pre-art caffeine boost. Opens at 9am.",
    timestamp: new Date(),
  }
};

export const getCategoryColor = (category: POI['category']): string => {
  const colors: Record<POI['category'], string> = {
    Food: 'from-orange-500 to-red-500',
    Art: 'from-purple-500 to-pink-500',
    Nature: 'from-green-500 to-emerald-500',
    Culture: 'from-amber-500 to-orange-500',
    Shopping: 'from-pink-500 to-rose-500',
    Nightlife: 'from-indigo-500 to-purple-500',
  };
  return colors[category];
};

export const getPlatformIcon = (platform: SourceVideo['platform']): string => {
  const icons: Record<SourceVideo['platform'], string> = {
    tiktok: '📱',
    douyin: '🎵',
    youtube: '▶️',
    rednote: '📕',
  };
  return icons[platform];
};
