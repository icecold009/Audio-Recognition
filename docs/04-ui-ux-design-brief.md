# UI/UX Design Brief

**Project:** DIY Shazam
**Version:** 1.1 — current implementation reference
**Date:** September 2026

---

## Brand Identity

### Concept & Tone

The app should feel **modern, warm, and musical** — evoking the sensation of sound and discovery without competing with the task. The primary action (recognizing music) is a front-and-center circular control that feels immediate and tactile. The visual language borrows the restraint of editorial tools and music apps while keeping the single-purpose experience clear.

**Tone keywords:** Immersive · Minimal · Tactile · Fast

---

## Color Palette

### Primary Light Theme (default)

The app defaults to a warm light theme, with dark mode available through the theme toggle.

```css
/* Backgrounds */
--color-bg:              #f4f1ea;   /* Warm paper */
--color-surface:         #fbfaf7;   /* Card/panel background */
--color-surface-2:       #ebe7df;   /* Elevated card / modals */
--color-surface-offset:  #e4dfd6;   /* Input fields, secondary panels */
--color-divider:         #d9d3ca;   /* Subtle separators */
--color-border:          #c9c1b5;   /* Form borders, card outlines */

/* Text */
--color-text:            #171817;   /* Primary graphite */
--color-text-muted:      #6d6a64;   /* Secondary labels, metadata */
--color-text-faint:      #9a948a;   /* Placeholder, disabled */

/* Accent — coral */
--color-primary:         #e35c43;   /* Main interactive accent */
--color-primary-hover:   #c94b36;
--color-primary-active:  #ad3d2d;
--color-primary-glow:    rgba(227,92,67,0.14);  /* Glow on mic button */

/* Result / Success */
--color-success:         #39715e;   /* Matched state */

/* Error */
--color-error:           #b14d42;   /* Mic denied, no match */

/* Waveform colors */
--color-wave-1:          #e35c43;   /* Active waveform bar */
--color-wave-2:          rgba(227,92,67,0.28);  /* Faded bars */
```

### Dark Theme (toggle)

```css
--color-bg:              #101211;
--color-surface:         #171918;
--color-surface-2:       #202321;
--color-surface-offset:  #252925;
--color-divider:         #303530;
--color-border:          #3a403a;
--color-text:            #f1eee8;
--color-text-muted:      #aaa79f;
--color-text-faint:      #777a74;
--color-primary:         #ff775d;
```

### Why This Palette?

Warm paper and graphite make the default state feel calm and tactile; coral supplies the moment of action without turning the page into a neon dashboard. The dark theme preserves the same hierarchy and accent relationships. Green remains reserved for a matched state so that recognition feedback stays distinct.

---

## Typography

### Font Pairing

| Role | Font | Weight | Source |
|------|------|--------|--------|
| **Display / Hero** | `Space Grotesk` | 500, 600, 700 | Google Fonts |
| **Body / UI** | `Manrope` | 400, 500, 600, 700 | Google Fonts |
| **Monospace** (timestamps, metadata) | `IBM Plex Mono` | 400, 500 | Google Fonts |

**Load snippet:**
```html
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link href="https://fonts.googleapis.com/css2?family=IBM+Plex+Mono:wght@400;500&family=Manrope:wght@400;500;600;700&family=Space+Grotesk:wght@500;600;700&display=swap" rel="stylesheet">
```

**Rationale:** Space Grotesk gives the hero and section headings a compact editorial voice. Manrope keeps supporting copy and controls readable, while IBM Plex Mono makes runtime metadata feel instrument-like and easy to scan.

### Type Scale (web app — responsive and shared)

```css
--text-display: clamp(3.5rem, 7.6vw, 6.5rem);    /* hero display */
--text-section:  clamp(2rem, 3.4vw, 3.25rem);    /* result section */
--text-feature:  clamp(1.15rem, 1.65vw, 1.45rem); /* card/control heading */
--text-body:     clamp(0.98rem, 1.15vw, 1.12rem);  /* body and UI copy */
--text-support:  clamp(0.82rem, 0.8rem + 0.15vw, 0.95rem);
--text-action:   clamp(0.8rem, 0.76rem + 0.1vw, 0.9rem);
--text-meta:     clamp(0.7rem, 0.68rem + 0.1vw, 0.78rem); /* runtime metadata */
```

The implemented rhythm uses a shared 18px label-to-heading gap, a responsive 20–28px heading-to-copy gap, and a responsive 48–76px copy-to-status gap. The full overrides live in [`web/static/typography.css`](../web/static/typography.css), so the type system can be reviewed independently from the larger legacy stylesheet.

---

## Iconography

- **Icon library:** Inline SVG icons — clean, consistent, 24px base grid
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
│  │          │  Blinding Lights             │  ← Space Grotesk, card title
│  │ Album    │  The Weeknd                  │  ← Manrope, supporting copy
│  │ Art      │  After Hours · 2019 · Pop    │  ← IBM Plex Mono, metadata
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

### Web UI Implementation Rules

The browser UI should follow these concrete responsive rules so it works cleanly on both laptops and phones:

- Use `box-sizing: border-box` on all elements so controls stay inside their containers.
- Use `clamp()` for page and component font sizes so text scales smoothly across screen sizes.
- Set the result image to `max-width: 100%` so album art or preview images never overflow narrow screens.
- Give primary buttons a `min-height: 44px` so they remain finger-tappable on touch devices.
- Use an `@media (max-width: 480px)` block for mobile-only rules.
- Make action buttons full-width on mobile so they are easier to tap than small inline buttons.
- Keep the main content width fluid with a readable desktop max-width rather than a fixed-width layout.

---

## Accessibility

- **Color contrast:** All text/background combinations meet WCAG AA (4.5:1 for body, 3:1 for large text)
- **Safe content rendering:** External links must use safe link handling (`rel="noopener noreferrer"` for new tabs), and dynamic content should be inserted without `innerHTML`.
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
