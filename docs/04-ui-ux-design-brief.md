# UI/UX Design Brief

**Project:** Shazam Clone  
**Version:** 1.0  
**Date:** June 2026

---

## Brand Identity

### Concept & Tone

The Shazam clone should feel **modern, dark, and musical** — evoking the sensation of sound and discovery. The primary action (recognizing music) should be front-and-center circle shape, immediate, and tactile. The UI borrows from the aesthetic of music apps (Spotify, Apple Music) but stays minimal enough to not distract from the single-purpose experience.

**Tone keywords:** Immersive · Minimal · Tactile · Fast

---

## Color Palette

### Primary Dark Theme (default)

The app defaults to **dark mode** as the primary theme, with light mode as an optional toggle.

```css
/* Backgrounds */
--color-bg:              #0d0d0f;   /* Near-black, deep dark */
--color-surface:         #13131a;   /* Card/panel background */
--color-surface-2:       #1a1a24;   /* Elevated card / modals */
--color-surface-offset:  #1f1f2e;   /* Input fields, secondary panels */
--color-divider:         #2a2a3a;   /* Subtle separators */
--color-border:          #2e2e42;   /* Form borders, card outlines */

/* Text */
--color-text:            #e8e8f0;   /* Primary — near-white, slight blue */
--color-text-muted:      #8888a0;   /* Secondary labels, metadata */
--color-text-faint:      #4a4a60;   /* Placeholder, disabled */

/* Accent — Electric Blue/Cyan (Shazam signature) */
--color-primary:         #1da1f2;   /* Main interactive accent */
--color-primary-hover:   #0d8dd6;
--color-primary-active:  #0a72ad;
--color-primary-glow:    rgba(29,161,242,0.15);  /* Glow on mic button */

/* Result / Success */
--color-success:         #1db954;   /* Spotify green — matched state */

/* Error */
--color-error:           #e84040;   /* Mic denied, no match */

/* Waveform colors */
--color-wave-1:          #1da1f2;   /* Active waveform bar */
--color-wave-2:          rgba(29,161,242,0.3);  /* Faded bars */
```

### Light Theme (toggle)

```css
--color-bg:              #f5f5f8;
--color-surface:         #ffffff;
--color-surface-2:       #f0f0f5;
--color-surface-offset:  #e8e8f0;
--color-divider:         #d8d8e4;
--color-border:          #c8c8da;
--color-text:            #12121a;
--color-text-muted:      #5a5a72;
--color-text-faint:      #9090a8;
--color-primary:         #0d8dd6;
```

### Why This Palette?

Blue-cyan is Shazam's signature color. Using deep near-black surfaces (not pure #000) prevents eye strain while maintaining drama. The electric blue accent on a near-black background creates strong contrast and a premium, music-app-native feel. Green is reserved exclusively for "match found" — users will immediately learn this visual language.

---

## Typography

### Font Pairing

| Role | Font | Weight | Source |
|------|------|--------|--------|
| **Display / Hero** | `Sora` | 700, 800 | Google Fonts |
| **Body / UI** | `Inter` | 400, 500, 600 | Google Fonts |
| **Monospace** (timestamps, metadata) | `JetBrains Mono` | 400 | Google Fonts |

**Load snippet:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=Sora:wght@700;800&family=Inter:wght@400;500;600&family=JetBrains+Mono:wght@400&display=swap" rel="stylesheet">
```

**Rationale:** Sora is geometric and modern — it feels tech-forward without being cold. Inter is the best-in-class UI sans-serif for reading at small sizes. JetBrains Mono adds a technical/musical metadata feel to secondary info.

### Type Scale (web app — capped at `--text-xl`)

```css
--text-xs:    clamp(0.75rem, 0.7rem + 0.25vw, 0.875rem);   /* 12–14px: timestamps */
--text-sm:    clamp(0.875rem, 0.8rem + 0.35vw, 1rem);       /* 14–16px: buttons, nav */
--text-base:  clamp(1rem, 0.95rem + 0.25vw, 1.125rem);      /* 16–18px: body */
--text-lg:    clamp(1.125rem, 1rem + 0.75vw, 1.5rem);       /* 18–24px: section headings */
--text-xl:    clamp(1.5rem, 1.2rem + 1.25vw, 2.25rem);      /* 24–36px: page title MAX */
```

---

## Iconography

- **Icon library:** [Lucide React](https://lucide.dev/) — clean, consistent, 24px base grid
- **Mic icon:** Custom animated SVG — not a Lucide icon; pulsing ring animation on LISTENING state
- **All icon-only buttons:** Must have `aria-label` and tooltip on hover/focus
- **Size:** 20px for nav/UI icons, 24px for action icons, 48px for the main mic CTA

---

## Spacing System

4px base unit, consistent with the Nexus system.

```
Micro:  4px   — icon gaps, badge padding
Small:  8–12px — form element internal padding
Base:   16px  — standard component padding
Medium: 24–32px — card padding, form groups
Large:  48–64px — section separation
Hero:   80–96px — page-level spacing
```

---

## Key Component Design

### Mic Button (Primary CTA)

This is the most important UI element. It must feel **alive and tactile**.

```
┌──────────────────────────────────┐
│ IDLE state:                      │
│    ○ pulse ring (slow, subtle)   │
│   ┌────────────────┐             │
│   │   🎙️   mic     │ 96px dia.   │
│   │   icon  SVG    │ border-radius: 50% │
│   └────────────────┘             │
│   Background: --color-primary    │
│   Glow: box-shadow 0 0 32px      │
│         --color-primary-glow     │
│                                  │
│ LISTENING state:                 │
│   Pulsing ring animation         │
│   Scale: 1.05 → 1.0 (1s loop)   │
│   Ring: expanding circle         │
│   Color: --color-primary         │
│                                  │
│ PROCESSING state:                │
│   Rotate spinner overlaid        │
│   Button disabled (no click)     │
└──────────────────────────────────┘
```

CSS:
```css
.mic-button {
  width: 96px;
  height: 96px;
  border-radius: 50%;
  background: var(--color-primary);
  box-shadow: 0 0 0 0 var(--color-primary-glow);
  animation: idle-pulse 2s ease-in-out infinite;
}

@keyframes idle-pulse {
  0%, 100% { box-shadow: 0 0 0 0 var(--color-primary-glow); }
  50%       { box-shadow: 0 0 24px 8px var(--color-primary-glow); }
}

.mic-button.listening {
  animation: listening-ring 1s ease-in-out infinite;
}

@keyframes listening-ring {
  0%   { transform: scale(1); box-shadow: 0 0 0 0 var(--color-primary-glow); }
  50%  { transform: scale(1.05); box-shadow: 0 0 0 16px rgba(29,161,242,0); }
  100% { transform: scale(1); box-shadow: 0 0 0 0 var(--color-primary-glow); }
}
```

### Waveform Visualizer

- 20–30 vertical bars, heights animated using Web Audio API `AnalyserNode` frequency data
- Bar color: `--color-wave-1`, faded non-active bars: `--color-wave-2`
- Container height: 64px
- Bars: 3px wide, 4px gap, `border-radius: 2px`
- Frame rate: 30fps via `requestAnimationFrame`

### Song Result Card

```
┌────────────────────────────────────────────┐
│  ┌──────────┐                              │
│  │          │  Blinding Lights             │  ← --text-lg, Sora 700
│  │ Album    │  The Weeknd                  │  ← --text-base, Inter 500
│  │ Art      │  After Hours · 2019 · Pop    │  ← --text-sm, text-muted
│  │ 80×80px  │                              │
│  └──────────┘                              │
│                                            │
│  [▶ Open on Spotify]  [Save]  [Try Again] │
└────────────────────────────────────────────┘
```

- Card background: `--color-surface-2`
- Border: `1px solid var(--color-border)`
- Border-radius: `--radius-lg` (12px)
- Album art: 80×80px, `border-radius: --radius-md`, `object-fit: cover`
- Entrance animation: slide up + fade in (200ms ease-out)

### History Item

```
┌──────────────────────────────────────┐
│ 🎵 [art 40px] Song Title      [×]   │
│               Artist · 2h ago        │
└──────────────────────────────────────┘
```

- Height: 64px
- Hover: `--color-surface-offset` background
- Delete × button: appears on hover (desktop) / always visible (mobile)
- Tap anywhere to navigate to `/song/:id`

---

## Motion & Animation Principles

1. **All transitions: 180–250ms ease-out** — fast enough to feel snappy, slow enough to be visible
2. **No instant show/hide** — use `opacity` + `transform` transitions
3. **Waveform bars:** `requestAnimationFrame` loop, smooth height changes via CSS transition on `height` property (30ms)
4. **Result card entrance:** `translateY(20px) opacity: 0` → `translateY(0) opacity: 1` (200ms)
5. **Mic button states:** Use `transition: all 250ms ease` on scale, box-shadow, background
6. **Reduce motion:** `@media (prefers-reduced-motion: reduce)` — disable all animations, keep functional transitions

---

## Responsive Breakpoints

| Breakpoint | Width | Layout changes |
|-----------|-------|----------------|
| Mobile S | 375px | Single column, mic button centered, bottom navbar |
| Mobile L | 430px | Same + slightly more padding |
| Tablet | 768px | Two-column history, wider cards |
| Desktop | 1024px+ | Max-width container (960px), centered layout |

**Mobile-first.** The primary use case (hearing music in public) is on mobile. Desktop is secondary.

---

## Accessibility

- **Color contrast:** All text/background combinations meet WCAG AA (4.5:1 for body, 3:1 for large text)
- **Focus indicators:** 2px `--color-primary` outline, 3px offset, on all interactive elements
- **Mic button aria-label:** "Identify song" (IDLE), "Stop listening" (LISTENING)
- **Waveform aria-live:** `aria-live="polite"` region announces "Listening…" and "Identifying…"
- **Result card:** `role="region"` with `aria-label="Recognition result"`
- **Color alone never conveys meaning** — green match state also uses a ✓ icon + text label

---

## Loading & Empty States

| State | Treatment |
|-------|-----------|
| History loading | Skeleton list items (shimmer animation) |
| Album art loading | Skeleton square with shimmer |
| Empty history | Music note icon + "No history yet" + "Identify a Song" button |
| No match | Search icon + "No match found" + retry copy |
| Network error | Wifi-off icon + "Check your connection" |

---

## Design Reference Inspirations

- **Shazam (iOS):** Core UX pattern, mic button prominence
- **Spotify:** Card design language, dark surfaces, album art treatment
- **Linear:** Minimal layout, fast interactions, keyboard-accessible
- **Apple Music:** Typography hierarchy, whitespace, smooth transitions

