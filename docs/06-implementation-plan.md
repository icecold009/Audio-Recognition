# Implementation Plan

**Project:** Shazam Clone  
**Version:** 1.0  
**Date:** June 2026  
**Author:** Shaurya Saria

---

## Overview

This plan describes the exact, sequential build order — from project scaffold to production deployment. Each phase builds on the previous one. Do not skip phases.

Estimated total: **7 weeks** (working solo, part-time).

---

## Prerequisites (Before Phase 1)

- [ ] Create RapidAPI account → subscribe to `shazam-core` API (free tier)
- [ ] Create Supabase project → note URL and keys
- [ ] Create Vercel account → connect to GitHub
- [ ] Install Node.js 20+, npm, Git
- [ ] Have a `.env.local` file template ready

---

## Phase 1 — Project Scaffold & Core UI (Days 1–4)

**Goal:** Running dev environment with the main recognition screen UI — no real API calls yet.

### Step 1.1 — Vite + React Setup
```bash
npm create vite@latest shazam-clone -- --template react
cd shazam-clone
npm install
npm install react-router-dom zustand
npm install -D tailwindcss @tailwindcss/vite
```

### Step 1.2 — Configure Tailwind v4
- Add `@import "tailwindcss"` to `src/index.css`
- Set up `vite.config.js` with `@tailwindcss/vite` plugin

### Step 1.3 — Folder Structure
Create the full `src/` directory structure as defined in the TRD:
```
src/components/ui/
src/components/layout/
src/components/recognition/
src/components/history/
src/components/auth/
src/pages/
src/hooks/
src/store/
src/lib/
src/utils/
```

### Step 1.4 — Design Tokens & Base CSS
- Add all CSS custom properties (colors, spacing, type scale, radius) to `src/index.css`
- Include dark/light mode variables
- Implement dark mode toggle (default: dark)

### Step 1.5 — Routing Setup
```jsx
// src/main.jsx
import { BrowserRouter, Routes, Route } from 'react-router-dom'
// Define all routes: /, /history, /song/:id, /auth/login, /auth/register, /settings
```

### Step 1.6 — Layout Components
- Build `Navbar` with logo, nav links, dark mode toggle
- Build `PageWrapper` with max-width container
- Add skip link for accessibility

### Step 1.7 — Home Page UI (Static)
- Build `MicButton` component with idle-pulse animation (no logic yet)
- Add placeholder result card (hardcoded data)
- Add listening state waveform placeholder (CSS bars, no audio)
- Wire state machine states manually via buttons for visual testing

**✅ Phase 1 done when:** `npm run dev` shows the home screen with animated mic button, no errors.

---

## Phase 2 — Audio Capture (Days 5–7)

**Goal:** Real microphone access, audio recording, waveform visualization.

### Step 2.1 — `useAudioCapture` Hook
```js
// src/hooks/useAudioCapture.js
// - getUserMedia({ audio: true })
// - Create MediaRecorder (webm or mp4 fallback)
// - Collect chunks for 10s
// - Return: { startRecording, stopRecording, audioBlob, isListening, error }
```

### Step 2.2 — Web Audio Waveform
```js
// src/components/recognition/ListeningWaveform.jsx
// - Create AudioContext + AnalyserNode
// - Connect MediaStream to analyser
// - requestAnimationFrame loop to read frequency data
// - Render 24 bars with height driven by frequency array
```

### Step 2.3 — Wire MicButton to Hook
- Click → `startRecording()`
- Stop button → `stopRecording()`
- 10s auto-stop timer
- Show waveform only during LISTENING state
- Disable mic button during PROCESSING

### Step 2.4 — Audio Utilities
```js
// src/utils/audioUtils.js
// blobToBase64(blob) → Promise<string>
// detectMimeType() → 'audio/webm' | 'audio/mp4'
```

**✅ Phase 2 done when:** Mic button captures real audio and returns a blob; waveform animates during recording.

---

## Phase 3 — Recognition API Integration (Days 8–11)

**Goal:** Real song recognition from captured audio.

### Step 3.1 — Vercel Project Init
```bash
npm install -g vercel
vercel login
vercel link   # link local project to Vercel
```

### Step 3.2 — Serverless API Route
```
api/
└── recognize.js    ← POST handler
```

```js
// api/recognize.js
// 1. Validate request method (POST only)
// 2. Parse { audio, mimeType } from body
// 3. Forward audio to RapidAPI shazam-core
// 4. Parse response → extract title, artist, album, art, links
// 5. Return clean JSON to client
// 6. Return 404 if no match, 500 on error
```

Set `RAPIDAPI_KEY` in Vercel environment variables.

### Step 3.3 — `useRecognition` Hook
```js
// src/hooks/useRecognition.js
// - Takes audioBlob
// - POSTs to /api/recognize
// - Returns { result, status, error }
// - status: 'idle' | 'processing' | 'matched' | 'no_match' | 'error'
```

### Step 3.4 — Wire Recognition to Home Page
- After `stopRecording()` → call `recognize(audioBlob)`
- Transition UI states: PROCESSING → MATCHED or NO_MATCH
- Render `ResultCard` component with real data
- Render `NoMatchUI` on 404 response

### Step 3.5 — Result Card Component
```jsx
// src/components/recognition/ResultCard.jsx
// Props: { title, artist, album, year, artUrl, spotifyUrl }
// Entrance animation: slide-up + fade-in
// Buttons: Open on Spotify (external), Save (to be wired in Phase 5), Try Again
```

**✅ Phase 3 done when:** App correctly identifies real songs from microphone input.

---

## Phase 4 — Authentication (Days 12–15)

**Goal:** User registration, login, logout with Supabase Auth.

### Step 4.1 — Supabase Client
```bash
npm install @supabase/supabase-js
```
```js
// src/lib/supabase.js
import { createClient } from '@supabase/supabase-js'
export const supabase = createClient(
  import.meta.env.VITE_SUPABASE_URL,
  import.meta.env.VITE_SUPABASE_ANON_KEY
)
```

### Step 4.2 — Supabase Database Setup
Run in Supabase SQL Editor:
1. Create `profiles` table + trigger (see schema doc)
2. Create `recognition_history` table + indexes
3. Enable RLS + all policies

### Step 4.3 — Auth Store (Zustand)
```js
// src/store/appStore.js
// State: { user, session, isLoading }
// Actions: setUser, setSession, clearAuth
// Subscribe to supabase.auth.onAuthStateChange
```

### Step 4.4 — Auth Pages
- `LoginForm` — email + password → `supabase.auth.signInWithPassword()`
- `RegisterForm` — email + password → `supabase.auth.signUp()`
- `AuthModal` (optional) — modal wrapper for both forms
- Handle errors inline (invalid credentials, email already in use)

### Step 4.5 — Route Guards
```jsx
// src/components/layout/ProtectedRoute.jsx
// Redirect to /auth/login if no session
// src/components/layout/GuestOnlyRoute.jsx  
// Redirect to / if already logged in
```

Apply to `/settings` (protected) and `/auth/*` (guest only).

### Step 4.6 — Navbar Auth State
- Show Login button when guest
- Show avatar + dropdown (Settings, Logout) when authenticated

**✅ Phase 4 done when:** Users can register, login, and logout. Route guards work correctly.

---

## Phase 5 — History Feature (Days 16–20)

**Goal:** Persistent history for authenticated users, session history for guests.

### Step 5.1 — Serverless History Routes
```
api/
├── recognize.js
└── history/
    ├── index.js    ← GET (list) + POST (save)
    └── [id].js     ← DELETE (remove item)
```

Each route:
1. Extract JWT from `Authorization: Bearer <token>`
2. Verify via `supabase.auth.getUser(token)`
3. Perform DB operation using service role client

### Step 5.2 — `useHistory` Hook
```js
// src/hooks/useHistory.js
// - fetchHistory(page) → paginated list
// - saveToHistory(songData) → inserts row
// - deleteHistoryItem(id) → removes row
// Authenticated: calls /api/history
// Guest: reads/writes sessionStorage array
```

### Step 5.3 — History Page
- Paginated list (20 items per page, "Load more" button)
- Skeleton loading state
- Empty state with CTA
- Guest upsell banner (non-intrusive)
- Delete button per item with confirm

### Step 5.4 — Song Detail Page
- Fetch single item from history store / API
- Full metadata display
- External streaming links
- Delete from history option

### Step 5.5 — Wire "Save" Button
- In `ResultCard`, wire "Save to History" button to `saveToHistory()`
- Auto-save if `profile.save_history === true` (skip button click)
- Show confirmation toast on save

**✅ Phase 5 done when:** Recognized songs are saved and viewable in history for logged-in users.

---

## Phase 6 — Settings & Account (Days 21–23)

**Goal:** Profile management, preferences, account deletion.

### Step 6.1 — Settings Page
- Display current email (read-only)
- Change password form → `supabase.auth.updateUser({ password })`
- Toggle: auto-save history → update `profiles.save_history`
- Delete all history → confirm modal → bulk DELETE
- Delete account → confirm with email input → `/api/account` DELETE endpoint

### Step 6.2 — Account Deletion Endpoint
```js
// api/account.js (DELETE)
// 1. Verify JWT
// 2. delete from recognition_history where user_id = $1
// 3. delete from profiles where id = $1
// 4. supabase.auth.admin.deleteUser(userId)  ← requires service role key
```

**✅ Phase 6 done when:** Users can manage their account and delete it.

---

## Phase 7 — Polish, Error States & Mobile QA (Days 24–27)

**Goal:** Production-quality UX on all states and devices.

### Step 7.1 — All Error States
- [ ] Mic permission denied
- [ ] No internet / fetch failed
- [ ] API rate limit (429 response)
- [ ] No match found
- [ ] Invalid song ID in URL
- [ ] Expired session (auto-redirect)
- [ ] Supabase unavailable (graceful degradation)

### Step 7.2 — Loading States
- [ ] Skeleton loaders on History page
- [ ] Spinner on mic button during PROCESSING
- [ ] Shimmer on album art during load
- [ ] Page-level loading state on initial auth check

### Step 7.3 — Mobile Testing
- Test at 375px (iPhone SE), 390px (iPhone 14), 768px (iPad)
- Verify mic button is thumb-reachable
- Test actual mic capture on mobile browser (Chrome Android + Safari iOS)
- Verify touch targets ≥ 44×44px

### Step 7.4 — Accessibility Audit
- [ ] Keyboard navigation (Tab through all interactive elements)
- [ ] Screen reader testing (VoiceOver on Mac, NVDA on Windows)
- [ ] Color contrast verification (Chrome DevTools)
- [ ] Focus trapping in modals

### Step 7.5 — Performance
- [ ] Run Lighthouse (target: Performance 90+, Accessibility 95+)
- [ ] Check initial bundle size (target: < 150KB gzipped)
- [ ] Verify LCP < 2.0s on 4G throttle
- [ ] Add `loading="lazy"` and dimensions to all `<img>` tags

**✅ Phase 7 done when:** Lighthouse scores ≥ 90, all states handled, mobile tested on real device.

---

## Phase 8 — Deployment (Days 28–30)

**Goal:** Live, production app on custom URL.

### Step 8.1 — Environment Variables
Add to Vercel dashboard → Project Settings → Environment Variables:
```
RAPIDAPI_KEY            = <your key>
RAPIDAPI_HOST           = shazam-core.p.rapidapi.com
SUPABASE_URL            = <your supabase url>
SUPABASE_SERVICE_ROLE_KEY = <service role key>
VITE_SUPABASE_URL       = <same supabase url>
VITE_SUPABASE_ANON_KEY  = <anon key>
VITE_API_BASE_URL       = https://your-app.vercel.app
```

### Step 8.2 — Vercel Deployment
```bash
vercel --prod
```
- Vercel auto-detects Vite; build command: `npm run build`; output: `dist/`

### Step 8.3 — Supabase CORS
- In Supabase Dashboard → Authentication → URL Configuration
- Add: `https://your-app.vercel.app` to allowed URLs
- Add: `https://your-app.vercel.app/**` to redirect URLs

### Step 8.4 — Verify Production
- [ ] HTTPS active (auto via Vercel)
- [ ] Mic works on production URL (requires HTTPS)
- [ ] Auth flow works (login, register, logout)
- [ ] History saves and loads
- [ ] No console errors

### Step 8.5 — GitHub CI/CD (Optional but Recommended)
```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]
jobs:
  lint-and-test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: '20' }
      - run: npm ci
      - run: npm run lint
      - run: npm run test
```

**✅ Phase 8 done when:** App is live at a Vercel URL, fully functional in production.

---

## Build Order Summary

| Phase | Focus | Duration | Key Milestone |
|-------|-------|----------|---------------|
| 1 | Scaffold + UI | Days 1–4 | Dev server running, home screen renders |
| 2 | Audio capture | Days 5–7 | Real mic → blob |
| 3 | Recognition API | Days 8–11 | Real song identified ✅ |
| 4 | Auth | Days 12–15 | Login/Register working |
| 5 | History | Days 16–20 | Songs saved to DB |
| 6 | Settings | Days 21–23 | Account management |
| 7 | Polish + QA | Days 24–27 | Lighthouse 90+ |
| 8 | Deployment | Days 28–30 | Live on Vercel 🚀 |

