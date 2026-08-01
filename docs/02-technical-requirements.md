# Technical Requirements Document

**Project:** Audio Recognition
**Status:** Current Flask implementation

## Architecture

Flask is the single browser application and API server. It serves the HTML shell, static JavaScript/CSS, and JSON endpoints from the same origin. The browser never calls recognition providers directly.

```text
Browser at /
  |-- /static/app.js and /static/style.css
  |-- POST /api/match -> Flask upload validation -> matcher backends
  `-- GET /api/status -> Flask runtime and configuration status

CLI at main.py -> shared shazam_project modules -> matcher backends
```

## Runtime stack

| Layer | Implementation |
|---|---|
| Browser UI | Flask templates, vanilla JavaScript, and CSS |
| Web server | Flask development server for local use; WSGI deployment is planned |
| Audio capture | Browser MediaRecorder and Web Audio API visualization |
| Audio decoding | WAV loader; optional FFmpeg conversion for browser uploads |
| Recognition | RapidAPI/Shazam, AcoustID, AudD, then local fingerprint index |
| Usage limits | Optional Supabase-backed counters plus process-local cooldown |

## Browser behavior

The page at `/` supports file upload, microphone capture with manual stop and a ten-second limit, waveform visualization, loading and error states, matched and no-match results, light/dark theme persistence, and session-only history. History is stored in the browser session and is not an authenticated database feature.

## API contract

`POST /api/match` accepts a multipart field named `file` and returns JSON with one of these statuses:

- `matched`: includes normalized `title`, `artist`, `album`, and optional `image` fields.
- `no_match`: no configured backend identified the audio.
- `no_token`: no recognition backend is configured.
- `rate_limited`: the request exceeded a configured limit.
- `error`: the upload, conversion, provider, or runtime path failed.

`GET /api/status` reports configured providers, optional `fpcalc` and FFmpeg availability, usage counters, cooldown, and upload/audio limits.

## Configuration and security

Provider keys and server configuration are loaded from the root `.env` file. The browser receives no provider keys or server secrets. Same-origin browser requests are accepted when `INTERNAL_API_SECRET` is enabled; optional external API clients must be explicitly listed in `CORS_ORIGINS`.

Uploads are bounded by `MAX_UPLOAD_BYTES` and `MAX_AUDIO_SECONDS`. Temporary files are removed after processing, and provider calls have bounded timeouts.

## Verification requirements

The required local checks are:

```powershell
python -m pytest -q
python -m coverage run --branch --source=shazam_project,web,scripts -m pytest -q
python -m coverage report --fail-under=50
```

The real-world benchmark remains separate from the application smoke tests and requires licensed source tracks, recorded clips, and provider credentials.
