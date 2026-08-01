# Browser Application Flow

**Project:** Audio Recognition
**Status:** Current Flask implementation

## Entry point

`python web/app.py` starts the complete local application. The browser opens `http://127.0.0.1:5000/`; Flask serves the page and its static assets, so browser requests to `/api/match` and `/api/status` remain same-origin.

## Recognition flow

1. The page loads and requests `/api/status` to display provider, tool, usage, and limit information.
2. The user either selects an audio file or grants microphone access.
3. Microphone capture displays a live waveform, supports manual stop, and auto-stops after ten seconds. The captured WebM file is submitted to `/api/match`.
4. File uploads and recordings show a loading state while Flask validates, optionally converts, and loads the audio.
5. The shared matcher tries configured backends in order: RapidAPI/Shazam, AcoustID, AudD, and the local fingerprint index.
6. The browser renders the normalized matched, no-match, rate-limited, or error response.
7. Matched results can be opened in a detail modal and are stored in session-only history when history is enabled.

## Supported page states

- Idle: upload and recording controls are available.
- Listening: waveform visualization and Stop control are shown.
- Processing: controls are disabled while recognition is submitted.
- Matched: title, artist, album, artwork when available, details, and history are shown.
- No match: a retry action explains that no backend identified the audio.
- Error or rate limited: a safe message and retry action are shown where retrying is meaningful.
- Settings: the privacy control enables or disables session history.

## API routes

| Route | Method | Purpose |
|---|---|---|
| `/` | GET | Canonical Flask browser entry point |
| `/static/*` | GET | Browser JavaScript, CSS, and other static assets |
| `/api/match` | POST | Multipart audio recognition endpoint |
| `/api/status` | GET | Runtime and configuration status endpoint |
