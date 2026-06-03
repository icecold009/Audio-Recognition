# Product Requirements Document (PRD)

**Project:** Shazam Clone — Music Recognition Web App  
**Author:** Shaurya Saria  
**Version:** 1.0  
**Date:** June 2026  
**Status:** Planning

---

## Overview

A full-stack web application that replicates core Shazam functionality — identifying songs from audio input via microphone or file upload, displaying song metadata (title, artist, album, artwork), and maintaining a personal history of identified tracks. The app targets music listeners who want quick, browser-native song identification without needing a native app.

---

## Problem Statement

Users frequently encounter music in public spaces — cafes, stores, events — and want to identify it instantly. Existing solutions require mobile app downloads or hardware access not always available on a desktop browser. This app delivers song recognition directly in the browser with zero installation friction.

---

## Goals

- Identify songs from real-time microphone input within 5-10 seconds
- Display rich song metadata: title, artist, album, release year, album art
- Maintain a per-user history of recognized songs
- Support both authenticated (persistent history) and guest (session-only) modes
- Provide a clean, mobile-responsive UI that works on desktop and mobile browsers

---

## Non-Goals (v1.0)

- Full music playback / streaming
- Lyrics display (deferred to v2)
- Offline recognition
- Native mobile app (web only)

---

## User Personas

### Primary — The Casual Listener
- Age: 16–30
- Behavior: Hears music in a public place, opens browser, wants an answer in seconds
- Needs: Fast recognition, clear result, no friction
- Frustration: Slow apps, too many steps, requires login just to identify

### Secondary — The Music Cataloguer
- Age: 20–40
- Behavior: Regularly identifies music and wants to track what they've discovered
- Needs: Persistent history, account management, ability to review past finds
- Frustration: History not saved between sessions, no organization

---

## Core Features

### F1 — Song Recognition
- **Trigger:** User clicks a "Identify" / microphone button
- **Flow:** Browser requests mic permission → captures audio → sends fingerprint to recognition API → displays result
- **Success state:** Song card with title, artist, album, artwork, year
- **Failure state:** "No match found" message with retry option
- **Timeout:** 10-second max listening window; auto-stops with feedback

### F2 — User Authentication
- **Registration:** Email + password
- **Login:** Email + password (with "remember me")
- **Guest mode:** Session-based history, no persistence
- **Auth provider:** Supabase Auth (email/password in v1; OAuth providers in v2)

### F3 — Recognition History
- **Authenticated users:** All recognized songs stored in database, displayed in reverse-chronological list
- **Guest users:** In-session list only, cleared on tab close
- **History card:** Album art thumbnail, song title, artist, timestamp of recognition
- **Actions per item:** View details

### F4 — Song Detail View
- Expanded view of a recognized song
- Fields: Title, Artist, Album, Genre (if available), Release Date, Album Art (large)
- External link to the song on a streaming platform (Spotify / Apple Music deep link)

### F5 — Settings & Account
- Update email / password
- Delete account + all history
- Toggle: Save history on/off (for privacy-conscious users)

---

## User Stories

| ID | As a… | I want to… | So that… |
|----|-------|-----------|---------|
| US-01 | Guest user | identify a song by tapping a button | I can know what song is playing without logging in |
| US-02 | Guest user | see my session's history | I can recall what I identified earlier today |
| US-03 | Registered user | have my history saved permanently | I can look back at songs I discovered weeks ago |
| US-04 | Registered user | remove items from my history | I can keep it clean and relevant |
| US-05 | Any user | see album art and metadata | I get more context than just a song title |
| US-06 | Any user | see a clear error if recognition fails | I know to try again or move closer to the source |
| US-07 | Registered user | delete my account | I can remove my data from the platform |

---

## Success Metrics

| Metric | Target |
|--------|--------|
| Recognition response time | < 5 seconds (P90) |
| Recognition accuracy | > 90% on popular tracks |
| Page load time (LCP) | < 2.0 seconds |
| Mobile usability score | > 90 (Lighthouse) |
| Guest → Register conversion | > 15% (stretch goal) |

---

## Constraints

- **API:** Shazam recognition via RapidAPI (free tier: 500 requests/month) — rate limiting required
- **Hosting:** Free tier (Vercel / Netlify for frontend; Supabase free for backend)
- **Browser support:** Chrome 90+, Firefox 88+, Safari 14+, Edge 90+
- **HTTPS required:** Microphone access requires secure context

---

## Milestones

| Phase | Deliverable | Target |
|-------|-------------|--------|
| Phase 1 | Core recognition UI + API integration | Week 1–2 |
| Phase 2 | Auth + persistent history | Week 3–4 |
| Phase 3 | History management + detail view | Week 5 |
| Phase 4 | Polish, error states, mobile QA | Week 6 |
| Phase 5 | Deployment + security hardening | Week 7 |

