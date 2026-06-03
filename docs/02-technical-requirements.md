# Technical Requirements Document (TRD)

**Project:** Shazam Clone  
**Author:** Shaurya Saria  
**Version:** 1.0  
**Date:** June 2026

---

## Architecture Overview

The application follows a **JAMstack-inspired architecture**: a static/SSR frontend communicates with a Supabase backend (PostgreSQL + Auth + Storage) and a third-party song recognition API via a serverless backend layer. No traditional server is required.

```
┌─────────────────────────┐      ┌──────────────────────┐
│     Browser Client      │─────▶│  Serverless Functions │
│   (React + Vite SPA)    │      │  (Vercel Edge/API)    │
└─────────────────────────┘      └──────────┬───────────┘
                                             │
                    ┌────────────────────────┼─────────────────────────┐
                    ▼                        ▼                         ▼
          ┌──────────────────┐   ┌──────────────────┐    ┌──────────────────────┐
          │   Supabase Auth  │   │ Supabase Postgres │    │ Shazam API (RapidAPI)│
          │  (JWT sessions)  │   │  (user history)   │    │  (song recognition)  │
          └──────────────────┘   └──────────────────┘    └──────────────────────┘
```

---

## Tech Stack

### Frontend

| Layer | Technology | Version | Rationale |
|-------|-----------|---------|-----------|
| Framework | React | 18.x | Component model ideal for state-heavy UI (listening states, results) |
| Build tool | Vite | 5.x | Fast HMR in dev, optimized production bundle |
| Routing | React Router | 6.x | Client-side routing for history/detail views |
| Styling | Tailwind CSS | 4.x | Utility-first, fast prototyping, small CSS bundle |
| State management | Zustand | 4.x | Lightweight, no boilerplate; simpler than Redux for this scale |
| HTTP client | Native `fetch` | — | No extra dependency; sufficient for REST calls |
| Audio capture | Web Audio API + `MediaRecorder` | — | Native browser API; no library needed |

### Backend / BaaS

| Layer | Technology | Rationale |
|-------|-----------|-----------|
| Auth | Supabase Auth | Email/password + future OAuth; JWT-based; free tier generous |
| Database | Supabase PostgreSQL | Managed Postgres; RLS built-in; free tier 500MB |
| Storage | Supabase Storage | For any user-uploaded content in future versions |
| Serverless functions | Vercel API Routes (Node.js) | Proxy layer to hide API keys from client; runs at edge |

### External APIs

| API | Provider | Purpose | Tier |
|-----|---------|---------|------|
| Shazam Recognition API | RapidAPI (`shazam-core`) | Audio fingerprint → song metadata | Free (500 req/mo) |
| Spotify Web API | Spotify | Deep links to songs (optional, no auth needed for links) | Free |

### Dev Tooling

| Tool | Purpose |
|------|---------|
| ESLint + Prettier | Code quality and formatting |
| Husky + lint-staged | Pre-commit hooks |
| Vitest | Unit testing |
| Playwright | E2E testing (Phase 4) |
| GitHub Actions | CI/CD pipeline |

---

## Frontend Architecture

### Component Structure

```
src/
├── components/
│   ├── ui/               # Reusable primitives (Button, Card, Badge, Spinner)
│   ├── layout/           # Navbar, Sidebar, PageWrapper
│   ├── recognition/      # MicButton, ResultCard, ListeningWaveform
│   ├── history/          # HistoryList, HistoryItem
│   └── auth/             # LoginForm, RegisterForm, AuthModal
├── pages/
│   ├── Home.jsx          # Main recognition screen
│   ├── History.jsx       # User history page
│   ├── SongDetail.jsx    # Expanded song view
│   ├── Auth.jsx          # Login/Register
│   └── Settings.jsx      # Account management
├── hooks/
│   ├── useAudioCapture.js   # Mic access + MediaRecorder logic
│   ├── useRecognition.js    # API call + state machine
│   └── useHistory.js        # CRUD operations on history
├── store/
│   └── appStore.js          # Zustand store
├── lib/
│   ├── supabase.js          # Supabase client init
│   └── api.js               # Internal API route wrappers
└── utils/
    ├── audioUtils.js        # Base64 encoding, blob conversion
    └── formatters.js        # Date/time formatting helpers
```

### State Machine — Recognition Flow

```
IDLE ──[click mic]──▶ REQUESTING_PERMISSION
                              │
                    ┌─────────┴──────────┐
                    ▼                    ▼
               DENIED               GRANTED
                  │                     │
              [show error]          LISTENING (max 10s)
                                        │
                              ┌─────────┴──────────┐
                              ▼                    ▼
                          TIMEOUT              PROCESSING
                              │                    │
                         [show msg]    ┌───────────┴──────────┐
                                       ▼                      ▼
                                   NO_MATCH               MATCHED
                                       │                      │
                                  [retry UI]            [show result]
                                                              │
                                                       [save to history]
                                                              │
                                                            IDLE
```

---

## Backend Architecture

### Serverless API Routes (Vercel)

| Route | Method | Description | Auth required |
|-------|--------|-------------|:---:|
| `/api/recognize` | POST | Receives audio blob, calls RapidAPI, returns song data | No |
| `/api/history` | GET | Returns paginated history for authenticated user | Yes |
| `/api/history` | POST | Saves a recognized song to user history | Yes |
| `/api/history/:id` | DELETE | Removes a history entry | Yes |
| `/api/account` | DELETE | Deletes user account + all history | Yes |

All routes validate JWT from `Authorization: Bearer <token>` header.  
API keys (`RAPIDAPI_KEY`, `SUPABASE_SERVICE_ROLE_KEY`) live in Vercel environment variables — never exposed to the client.

---

## Audio Capture Specification

1. Request `getUserMedia({ audio: true })` on user gesture (required by browsers)
2. Create `MediaRecorder` with `mimeType: 'audio/webm;codecs=opus'`
3. Collect chunks for up to **10 seconds** OR until user stops manually
4. Concatenate chunks into a single `Blob`
5. Convert blob to Base64 string
6. POST to `/api/recognize` as JSON body: `{ audio: "<base64>", mimeType: "audio/webm" }`

Fallback: If `audio/webm` is unsupported (Safari), use `audio/mp4`.

---

## Database Design (see separate schema doc)

Tables: `profiles`, `recognition_history`  
Auth: managed by `auth.users` (Supabase built-in)  
RLS: All tables enforce row-level security — users can only access their own rows.

---

## Environment Variables

### Client-side (Vite — prefix `VITE_`)
```
VITE_SUPABASE_URL=
VITE_SUPABASE_ANON_KEY=
VITE_API_BASE_URL=
```

### Server-side (Vercel — never exposed to client)
```
RAPIDAPI_KEY=
RAPIDAPI_HOST=shazam-core.p.rapidapi.com
SUPABASE_URL=
SUPABASE_SERVICE_ROLE_KEY=
```

---

## Performance Targets

| Metric | Target |
|--------|--------|
| Initial bundle size (gzipped) | < 150 KB |
| Largest Contentful Paint | < 2.0s |
| Time to Interactive | < 3.5s |
| Recognition API round-trip | < 5s (P90) |
| Supabase query (history list) | < 300ms |

---

## Browser Compatibility

| Feature | Chrome | Firefox | Safari | Edge |
|---------|--------|---------|--------|------|
| `getUserMedia` | ✅ 90+ | ✅ 88+ | ✅ 14.1+ | ✅ 90+ |
| `MediaRecorder` | ✅ | ✅ | ✅ 14.1+ | ✅ |
| `audio/webm` | ✅ | ✅ | ❌ (use mp4) | ✅ |
| Web Audio API | ✅ | ✅ | ✅ | ✅ |

Safari requires `audio/mp4` fallback — detect via `MediaRecorder.isTypeSupported()`.

