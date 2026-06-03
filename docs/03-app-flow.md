# App Flow Document

**Project:** Shazam Clone  
**Version:** 1.0  
**Date:** June 2026

---

## Overview

This document describes every screen the user can visit and the transitions between them. Navigation is client-side (React Router). There are two user modes: **Guest** (no login, session-only history) and **Authenticated** (persistent history).

Error handling should stay user-safe: auth failures and permission errors must show brief, generic messages and should not expose internal stack traces, provider names, or backend implementation details.

---

## Site Map

```
App
├── / (Home — Recognition Screen)          [ALL users]
├── /history                               [ALL users — guest = session only]
├── /song/:id                              [ALL users — song detail view]
├── /auth
│   ├── /auth/login                        [Guest only — redirect if logged in]
│   └── /auth/register                     [Guest only — redirect if logged in]
├── /settings                              [Authenticated only]
└── * (Not Found → redirect to /)
```

---

## Navigation Structure

### Navbar (persistent, all pages)

```
┌──────────────────────────────────────────────────────────┐
│  🎵 Shazam Clone    [Home]  [History]   [Login / Avatar] │
└──────────────────────────────────────────────────────────┘
```

- **Logo / Home** → `/`
- **History** → `/history`
- **Login** (guest) → `/auth/login`
- **Avatar dropdown** (authenticated) → Settings | Logout

---

## Screen-by-Screen Flow

---

### Screen 1: Home — Recognition Screen (`/`)

**Purpose:** The primary action screen. The user identifies music here.

**Initial State (IDLE):**
```
┌──────────────────────────────────┐
│         What's playing?          │
│                                  │
│         ┌──────────┐             │
│         │    🎙️   │  ← big tap  │
│         │ Identify │    button   │
│         └──────────┘             │
│                                  │
│  [Last recognized: Song Name]    │  ← only if history exists
└──────────────────────────────────┘
```

**Transitions from IDLE:**
- Tap mic button → request microphone permission
  - Permission DENIED → show inline error banner: "Microphone access denied. Please allow mic access in browser settings."
  - Permission GRANTED → transition to LISTENING state

**LISTENING state (up to 10 seconds):**
```
┌──────────────────────────────────┐
│         Listening...             │
│                                  │
│    ~~~~~ WAVEFORM ANIMATION ~~~~ │
│                                  │
│      ██  ██  ███  ██  ██        │
│                                  │
│         [  Stop  ]               │
│    0s ─────────────── 10s        │
└──────────────────────────────────┘
```
- Progress bar fills over 10 seconds
- User can tap Stop early
- After 10s OR Stop → transition to PROCESSING

**PROCESSING state:**
```
┌──────────────────────────────────┐
│         Identifying...           │
│         ⠋ spinner                │
└──────────────────────────────────┘
```

**MATCHED state → Result Card appears:**
```
┌──────────────────────────────────┐
│  ┌────────┐  Blinding Lights     │
│  │ [art]  │  The Weeknd          │
│  │        │  After Hours · 2019  │
│  └────────┘                      │
│                                  │
│   [▶ Open on Spotify]            │
│   [Save to History]  [Try Again] │
└──────────────────────────────────┘
```

**NO_MATCH state:**
```
┌──────────────────────────────────┐
│   🔍 No match found              │
│   Try moving closer to the       │
│   audio source and try again.    │
│                                  │
│         [Try Again]              │
└──────────────────────────────────┘
```

**Flow Diagram:**
```
[IDLE] ──tap──▶ [PERMISSION REQUEST]
                       │
            ┌──denied──┴──granted──┐
            ▼                      ▼
        [ERROR]               [LISTENING]
                                   │
                         ┌─stop/timeout─┐
                         ▼             ▼
                    [PROCESSING]   [PROCESSING]
                         │
               ┌─match───┴───no match──┐
               ▼                       ▼
           [RESULT CARD]          [NO MATCH UI]
               │
         ┌─────┴──────────┐
         ▼                ▼
  [Save → History]   [Spotify link]
         │
       [IDLE]
```

---

### Screen 2: History (`/history`)

**Purpose:** View all previously recognized songs.

**Authenticated user — full history:**
```
┌─────────────────────────────────────┐
│  Recognition History (23 songs)     │
│                                     │
│  ┌─────────────────────────────┐    │
│  │ 🎵 Blinding Lights          │    │
│  │    The Weeknd · 2 hours ago │ ×  │
│  └─────────────────────────────┘    │
│  ┌─────────────────────────────┐    │
│  │ 🎵 Levitating               │    │
│  │    Dua Lipa · Yesterday     │ ×  │
│  └─────────────────────────────┘    │
│  ...                                │
│  [Load more]                        │
└─────────────────────────────────────┘
```

**Guest user — session history:**
```
┌─────────────────────────────────────┐
│  This Session (3 songs)             │
│  ─────────────────────────────────  │
│  Sign in to save your history       │
│  across sessions.    [Sign In]      │
│  ─────────────────────────────────  │
│  [session list items...]            │
└─────────────────────────────────────┘
```

**Empty state (no history):**
```
┌─────────────────────────────────────┐
│         📋 No history yet           │
│  Start identifying songs and        │
│  they'll appear here.               │
│                                     │
│         [Identify a Song]           │
└─────────────────────────────────────┘
```

**Transitions:**
- Tap a history item → `/song/:id`
- Tap × on a history item → confirm delete modal → remove from list
- Tap "Identify a Song" → `/`

---

### Screen 3: Song Detail (`/song/:id`)

**Purpose:** Expanded view of a single recognized song.

```
┌───────────────────────────────────────┐
│  ← Back                               │
│                                       │
│         ┌──────────────┐              │
│         │              │              │
│         │  Album Art   │              │
│         │   (large)    │              │
│         └──────────────┘              │
│                                       │
│  Blinding Lights                      │
│  The Weeknd                           │
│  After Hours                          │
│  Pop · 2019                           │
│                                       │
│  Recognized: 14 Jun 2026, 4:30 PM    │
│                                       │
│  [▶ Open on Spotify]                  │
│  [🗑️ Remove from History]             │
└───────────────────────────────────────┘
```

**Transitions:**
- Back button → `/history` (or browser back)
- "Open on Spotify" → external link (new tab)
- "Remove from History" → confirm → redirect to `/history`

---

### Screen 4: Auth (`/auth/login`, `/auth/register`)

**Login:**
```
┌────────────────────────────────┐
│  Welcome back                  │
│                                │
│  Email     [__________________]│
│  Password  [__________________]│
│                                │
│  [Log In]                      │
│                                │
│  Don't have an account?        │
│  [Create one]                  │
└────────────────────────────────┘
```

**Register:**
```
┌────────────────────────────────┐
│  Create account                │
│                                │
│  Email     [__________________]│
│  Password  [__________________]│
│  Confirm   [__________________]│
│                                │
│  [Sign Up]                     │
│                                │
│  Already have an account?      │
│  [Log In]                      │
└────────────────────────────────┘
```

**Transitions:**
- Successful login → `/` (or previous page)
- Successful register → `/` (auto-logged in)
- Switch between Login ↔ Register → in-page tab or link

---

### Screen 5: Settings (`/settings`)

**Purpose:** Account management for authenticated users only.

```
┌────────────────────────────────────┐
│  Settings                          │
│                                    │
│  Account                           │
│  ──────────────────────────────    │
│  Email:  sariashaurya09@gmail.com  │
│          [Change Email]            │
│          [Change Password]         │
│                                    │
│  Preferences                       │
│  ──────────────────────────────    │
│  Auto-save history  [Toggle ON]    │
│                                    │
│  Danger Zone                       │
│  ──────────────────────────────    │
│  [Delete All History]              │
│  [Delete Account]  ← destructive   │
└────────────────────────────────────┘
```

---

## Route Guards

| Route | Guest | Authenticated |
|-------|:-----:|:-------------:|
| `/` | ✅ | ✅ |
| `/history` | ✅ (session only) | ✅ (persistent) |
| `/song/:id` | ✅ | ✅ |
| `/auth/login` | ✅ | Redirect → `/` |
| `/auth/register` | ✅ | Redirect → `/` |
| `/settings` | Redirect → `/auth/login` | ✅ |

---

## Error & Edge Case Flows

| Scenario | Handling |
|----------|---------|
| No internet during recognition | Show toast: "No internet connection. Please check your network." |
| API rate limit exceeded (429) | Show friendly message: "Too many requests. Please wait a moment." |
| Supabase down | Show banner: "History temporarily unavailable." — core recognition still works |
| Session expired | Auto-redirect to `/auth/login` with message "Your session has expired." |
| Invalid song ID in URL | Show 404 state with "Song not found" and link back to History |
| Mic permission asked, then revoked mid-session | Gracefully stop, show permission error, return to IDLE |

