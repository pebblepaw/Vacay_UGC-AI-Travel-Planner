

# VACAY - AI Travel Itinerary Planner

## Overview
A bold, playful travel planning app that transforms short-form video content into beautiful, interactive itineraries. Users land directly on a sample Tokyo trip experience, showcasing all core features.

---

## Design System

**Visual Identity**
- **Colors**: Vibrant gradient palette (coral → magenta → violet) inspired by social media aesthetics
- **Typography**: Modern, rounded sans-serif (playful yet readable)
- **Cards**: Frosted glass effects with subtle shadows
- **Animations**: Smooth transitions, micro-interactions on hover/tap
- **Dark/Light mode**: Default to light with optional dark toggle

---

## Pages & Components

### 1. Landing Experience (Sample Trip View)
The app opens directly to an interactive "Hidden Gems of Tokyo" sample itinerary.

**Layout**: Three-column responsive design
- **Left**: Interactive Mapbox map (60% width on desktop)
- **Center/Right**: Itinerary content area
- **Bottom**: Floating chat toggle button

---

### 2. Interactive Map View
**Features**:
- Mapbox GL JS integration with your API key
- Custom animated pins (pulsing markers with category-specific icons)
- Smooth "fly-to" animations when selecting POIs
- Route lines connecting stops with estimated travel times
- Click-to-expand: Pins reveal mini-cards with photo, name, vibe

**Interactions**:
- Hover: Pin grows slightly, shows tooltip
- Click: Map flies to location, sidebar scrolls to matching card
- Drag: Standard map panning

---

### 3. Horizontal Scroll Cards
**Location Cards** (horizontally scrollable strip above the map or as a standalone section):
- Large featured image (video thumbnail placeholder)
- Location name + category badge (Food, Art, Nature)
- "Vibe" description extracted from video context
- Time slot indicator
- Source video indicator (TikTok/Douyin/YouTube icon)

**Snap-to-card** scrolling with smooth momentum

---

### 4. Day-by-Day Timeline View
**Structured List**:
- Day headers (Day 1, Day 2, etc.) with date
- Vertical timeline connector
- POI cards in sequence with:
  - Time slot (10:00 - 13:00)
  - Travel time to next stop (🚶 15 min walk, 🚕 10 min taxi)
  - Expandable details
- Accommodation card at end of each day

**Interactions**:
- Click any POI to highlight on map
- Drag-to-reorder (visual only in MVP)
- Collapse/expand individual days

---

### 5. Agentic Chat Sidebar
**Persistent Side Panel** (slide-in from right):
- Chat message bubbles (user + AI agent)
- Mock conversational AI for itinerary adjustments
- **Human-in-the-Loop Interrupts**: Special UI cards for decisions
  - Hotel selection cards with options A/B/C
  - "Approve" / "Reject" / "Show more options" buttons
  - Status indicators: "Waiting for your input", "Approved ✓"

**Sample Interactions** (mock responses):
- "Can you find a cheaper hotel?" → Shows 3 mock options
- "Replace the ramen spot with sushi" → Swaps POI in itinerary
- "Add a coffee shop near TeamLab" → Suggests mock option

---

### 6. URL Input Modal/Page
**Accessible via floating "+" button**:
- Input field for video URLs (TikTok, Douyin, Rednote, YouTube)
- Paste detection with platform auto-detection
- "Add to Collection" dropdown
- Mock processing animation (for future API integration)

---

### 7. Trip Header & Meta
**Top Bar**:
- Trip title ("Hidden Gems of Tokyo")
- Duration badge (3 Days)
- Source videos count (5 videos)
- Share button
- Edit/Settings menu

---

## Navigation Structure

```
/ (Home) → Sample Tokyo Itinerary
├── Map View Tab
├── Timeline View Tab  
├── Cards Gallery Tab
├── Chat Sidebar (toggle)
└── Add URL Modal
```

---

## Data Structure (Using Your JSON)

The app will be pre-loaded with your sample itinerary JSON:
- `trip_id`, `title`, `source_videos`
- `days[]` with `pois[]` (coordinates, images, vibes)
- `accommodation` details
- `chat_state` for human-in-the-loop demos

---

## Technical Approach

1. **Mapbox Integration**: React-map-gl wrapper for Mapbox GL JS
2. **State Management**: React Context for trip data + chat state
3. **Mock Data**: JSON files mimicking your sample structure
4. **Responsive**: Mobile-first with slide-up map on small screens
5. **Animations**: Framer Motion for smooth transitions

---

## Deliverables

1. ✅ Complete React + Tailwind UI with Shadcn components
2. ✅ Mapbox map with custom pins and animations
3. ✅ Three synchronized views (Map, Timeline, Cards)
4. ✅ Mock chat sidebar with human-in-the-loop cards
5. ✅ Bold, playful design matching TikTok/Instagram aesthetic
6. ✅ Mobile-responsive layout
7. ✅ Sample Tokyo itinerary pre-loaded

**Ready for future integration** with your Python/LangGraph backend via API endpoints.

