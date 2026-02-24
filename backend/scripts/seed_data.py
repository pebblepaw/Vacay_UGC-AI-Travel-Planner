
import asyncio
from backend.storage.local_storage import local_storage
from backend.models.schemas import Trip

sample_trip_data = {
  "trip_id": "tokyo-vibe-001",
  "title": "Hidden Gems of Tokyo",
  "source_videos": [
    { "platform": "tiktok", "url": "https://tiktok.com/@user/video1", "title": "Best ramen in Shinjuku 🍜" },
    { "platform": "douyin", "url": "https://douyin.com/video2", "title": "新宿の隠れ家ラーメン" },
    { "platform": "youtube", "url": "https://youtube.com/shorts/abc123", "title": "TeamLab is INSANE" },
    { "platform": "rednote", "url": "https://xiaohongshu.com/note3", "title": "原宿购物攻略" },
    { "platform": "tiktok", "url": "https://tiktok.com/@user/video4", "title": "Tokyo nightlife guide" },
  ],
  "days": [
    {
      "day_number": 1,
      "date": "2024-04-15",
      "pois": [
        {
          "id": "poi_1",
          "name": "TeamLab Borderless",
          "category": "Art",
          "coords": [139.7834, 35.6267],
          "img": "https://images.unsplash.com/photo-1549887534-1541e9326642?w=600&h=400&fit=crop",
          "time_slot": "10:00 - 13:00",
          "vibe": "Immersive digital art featured in 5 of your saved videos. Mind-bending infinity rooms and flowing water projections.",
          "priority": "high",
          "intensity": "normal",
          "visit_duration": 180
        },
        {
          "id": "poi_2",
          "name": "Shinjuku Gyoen Ramen",
          "category": "Food",
          "coords": [139.7100, 35.6850],
          "img": "https://images.unsplash.com/photo-1557872943-16a5ac26437e?w=600&h=400&fit=crop",
          "time_slot": "13:30 - 14:30",
          "vibe": "The 'secret ramen' spot from the Douyin clip. Rich tonkotsu broth with homemade noodles.",
          "priority": "normal",
          "intensity": "normal",
          "visit_duration": 60
        },
        {
          "id": "poi_3",
          "name": "Shinjuku Gyoen Garden",
          "category": "Nature",
          "coords": [139.7100, 35.6852],
          "img": "https://images.unsplash.com/photo-1528360983277-13d401cdc186?w=600&h=400&fit=crop",
          "time_slot": "15:00 - 17:00",
          "vibe": "Serene Japanese garden perfect for afternoon strolls. Cherry blossoms in spring!",
          "priority": "low",
          "intensity": "low",
          "visit_duration": 120
        }
      ]
    },
    {
      "day_number": 2,
      "date": "2024-04-16",
      "pois": [
        {
          "id": "poi_4",
          "name": "Harajuku Takeshita Street",
          "category": "Shopping",
          "coords": [139.7028, 35.6716],
          "img": "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600&h=400&fit=crop",
          "time_slot": "10:00 - 12:00",
          "vibe": "Kawaii culture central! Crepe shops, vintage finds, and street fashion galore.",
          "priority": "normal",
          "intensity": "high",
          "visit_duration": 120
        },
        {
          "id": "poi_5",
          "name": "Meiji Shrine",
          "category": "Culture",
          "coords": [139.6993, 35.6764],
          "img": "https://images.unsplash.com/photo-1583766395091-2eb9994ed094?w=600&h=400&fit=crop",
          "time_slot": "12:30 - 14:00",
          "vibe": "Peaceful forest oasis in the heart of Tokyo. Traditional Shinto shrine experience.",
          "priority": "high",
          "intensity": "low",
          "visit_duration": 90
        },
        {
          "id": "poi_6",
          "name": "Shibuya Crossing",
          "category": "Culture",
          "coords": [139.7016, 35.6595],
          "img": "https://images.unsplash.com/photo-1542051841857-5f90071e7989?w=600&h=400&fit=crop",
          "time_slot": "14:30 - 15:30",
          "vibe": "The world's busiest intersection! Watch from Starbucks for the best view.",
          "priority": "normal",
          "intensity": "low",
          "visit_duration": 60
        },
        {
          "id": "poi_7",
          "name": "Golden Gai",
          "category": "Nightlife",
          "coords": [139.7050, 35.6938],
          "img": "https://images.unsplash.com/photo-1554797589-7241bb691973?w=600&h=400&fit=crop",
          "time_slot": "19:00 - 23:00",
          "vibe": "Tiny bars, big vibes. Over 200 micro-bars in narrow alleys. The TikTok nightlife spot!",
          "priority": "normal",
          "intensity": "normal",
          "visit_duration": 240
        }
      ]
    },
    {
      "day_number": 3,
      "date": "2024-04-17",
      "pois": [
        {
          "id": "poi_8",
          "name": "Tsukiji Outer Market",
          "category": "Food",
          "coords": [139.7706, 35.6654],
          "img": "https://images.unsplash.com/photo-1553621042-f6e147245754?w=600&h=400&fit=crop",
          "time_slot": "07:00 - 09:00",
          "vibe": "Fresh sushi breakfast! The early bird catches the best tuna.",
          "priority": "high",
          "intensity": "high",
          "visit_duration": 120
        },
        {
          "id": "poi_9",
          "name": "Senso-ji Temple",
          "category": "Culture",
          "coords": [139.7966, 35.7148],
          "img": "https://images.unsplash.com/photo-1545569341-9eb8b30979d9?w=600&h=400&fit=crop",
          "time_slot": "10:00 - 12:00",
          "vibe": "Tokyo's oldest temple with iconic red lantern gate. Don't miss the shopping street!",
          "priority": "high",
          "intensity": "low",
          "visit_duration": 120
        },
        {
          "id": "poi_10",
          "name": "Akihabara Electric Town",
          "category": "Shopping",
          "coords": [139.7731, 35.7023],
          "img": "https://images.unsplash.com/photo-1528164344705-47542687000d?w=600&h=400&fit=crop",
          "time_slot": "14:00 - 17:00",
          "vibe": "Anime paradise! Arcades, maid cafes, and retro game shops everywhere.",
          "priority": "normal",
          "intensity": "high",
          "visit_duration": 180
        }
      ]
    }
  ],
  "accommodation": {
    "name": "Shinjuku Airbnb High-rise",
    "price_per_night": 145,
    "status": "Found via Playwright - Best Match",
    "img": "https://images.unsplash.com/photo-1522708323590-d24dbb6b0267?w=600&h=400&fit=crop",
    "coords": [139.6917, 35.6895]
  }
}

async def seed():
    trip = Trip(**sample_trip_data)
    await local_storage.save_trip(trip)
    print(f"✅ Seeded trip: {trip.trip_id}")

if __name__ == "__main__":
    asyncio.run(seed())
