# Knowtis Frontend

Modern, premium web interface for Knowtis - AI-powered academic communication assistant.

## Features

- 🎨 **Modern Design System** - Pastel colors, smooth animations, premium feel
- 🏗️ **Component Library** - Reusable UI components (Button, Card, Badge, etc.)
- 📱 **Responsive Layout** - Mobile-first design with sidebar navigation
- ⚡ **Real-time Updates** - WebSocket support for live academic events
- 🎯 **Sticky Note Cascade** - Signature cascading UI for academic events
- 🌈 **Event Taxonomy** - Visual categorization (Deadline, Alert, Event, Info)
- 💾 **State Management** - Zustand for efficient state handling
- 🔒 **Type Safety** - Full TypeScript implementation

## Design System

### Colors
- **Primary**: #4F46E5 (Indigo)
- **Accent**: #6366F1 (Light Indigo)
- **Background**: #F8F7FF (Soft Purple)
- **Urgency Colors**:
  - Critical: #FFB3A7 (Soft Coral)
  - High: #FFF3B0 (Pastel Yellow)
  - Medium: #B8F0D4 (Mint Green)
  - Low: #D4C5F9 (Lavender)

### Components
- Buttons (primary, secondary, tertiary, ghost, danger)
- Cards (interactive, hover effects)
- Sticky Notes (urgency-based colors)
- Badges (multiple variants)
- Input fields

## Installation

```bash
cd frontend
npm install
```

## Development

```bash
npm run dev
```

Open [http://localhost:3000](http://localhost:3000) with your browser to see the result.

## Build

```bash
npm run build
npm start
```

## File Structure

```
src/
├── app/                    # Next.js app directory
├── components/             # React components
│   ├── ui/                # Reusable UI components
│   ├── layout/            # Layout components (Navbar, Sidebar)
│   └── dashboard/         # Dashboard-specific components
├── lib/                   # Utility functions
│   ├── api.ts            # API client
│   └── store.ts          # Zustand state management
├── styles/               # Global styles
└── types/                # TypeScript types
```

## Environment Variables

Create `.env.local`:

```
NEXT_PUBLIC_API_BASE_URL=http://localhost:8000/api
NEXT_PUBLIC_APP_URL=http://localhost:3000
```

## Tech Stack

- **Framework**: Next.js 14
- **UI Library**: React 18
- **Styling**: Tailwind CSS
- **State**: Zustand
- **Animations**: Framer Motion
- **HTTP Client**: Axios
- **Icons**: Lucide React
- **Language**: TypeScript

## Deployment

Deploy on Vercel:

```bash
npm run build
vercel deploy
```

## Pages

- `/dashboard` - Main dashboard with Cascade UI
- `/groups` - WhatsApp group management
- `/events` - All academic events
- `/reminders` - Scheduled reminders
- `/analytics` - Analytics and insights
- `/settings` - User settings

## Next Steps

1. Implement WebSocket for real-time updates
2. Build authentication pages (login, register)
3. Add API integration for events
4. Implement dark mode toggle
5. Add mobile app views

## License

MIT
