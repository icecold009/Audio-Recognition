<div align="center">

[![CI](https://github.com/icecold009/audio-recognition/actions/workflows/ci.yml/badge.svg)](https://github.com/icecold009/audio-recognition/actions/workflows/ci.yml)
<br/>

**Identify any song from your microphone or an audio file.**  
Validated audio pipeline · Multi-backend matching · Flask web UI · Terminal output


</div>

***
<div align="center">
  <h1 style="margin:0;padding:0">Audio Recognition</h1>
  <p style="margin:4px 0 8px;color:#1E90FF">Identify songs from your microphone or an audio file with validated multi-backend matching</p>
</div>

## Overview
DIY Shazam captures audio from the CLI microphone/file path or the Flask browser UI, normalizes it through one bounded audio pipeline, and identifies tracks using RapidAPI/Shazam, AcoustID, AudD, or local spectrogram peaks and constellation hash pairs. FFT output is a diagnostic visualization only; it is not the recognition algorithm. Flask serves the complete browser UI and JSON API from one origin.

## Performance

| Metric | Result |
|--------|--------|
| Average recognition time (RapidAPI backend) | Not measured; real-world benchmark pending |
| Average recognition time (AudD backend) | Not measured; real-world benchmark pending |
| Test set accuracy | Not measured; real-world benchmark pending |
| Minimum audio duration | 1 s by default (configurable) |
| Maximum audio duration | 30 s by default (configurable) |
| Maximum upload size | 10 MiB by default (configurable) |
| Platforms tested | Not established by this branch's validation |

## Architecture
```mermaid
flowchart LR
  A[CLI / Flask Browser UI] --> B[Audio Input\n(mic or upload)]
  B --> C[Validate and normalize\nmono float32 / internal rate]
  C --> D[FFT diagnostic only]
  C --> E[Write 16-bit PCM WAV temp]
  E --> F{Matcher Backends}
  F -->|RapidAPI| G[Shazam]
  F -->|AcoustID| H[AcoustID]
  F -->|AudD| I[AudD]
  F -->|Local hashes| J[Peak/hash index]
  G & H & I & J --> K[Normalized Result]
  K --> L[Display (CLI) / JSON (Web)]
  classDef blue fill:#ffffff,stroke:#1E90FF,stroke-width:2px,color:#1E90FF;
  class A,B,C,D,E,F,G,H,I,J,K,L blue;
```
Theme: black / white / blue — white nodes with a professional DodgerBlue accent (#1E90FF). The browser UI is served directly by Flask; there is no separate browser bundle.

## Quickstart
1) Create & activate a venv:
```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
```
2) Install runtime deps:
```powershell
pip install -r requirements.txt
```
3) Add configuration:
```powershell
copy .env.example .env
# edit .env to add AUDD_API_TOKEN or other keys
```
4) Run CLI when terminal recognition is needed:
```powershell
python main.py
```
5) Run the complete browser UI and API from Flask:
```powershell
python web/app.py
# open http://127.0.0.1:5000
```

## Project Structure
Core source modules now live under `shazam_project/`:

- `shazam_project/config.py`
- `shazam_project/recorder.py`
- `shazam_project/fft_analyze.py`
- `shazam_project/matcher.py`
- `shazam_project/display.py`

Entrypoints remain:

- `main.py` (CLI)
- `web/app.py` (canonical Flask browser app and API)
- `web/templates/index.html` and `web/static/` (same-origin browser assets)

## Configuration
Supported env vars (see `shazam_project.config.load_config()`): `AUDD_API_TOKEN`, `ACOUSTID_API_KEY`, `FP_CALC_PATH`, `RAPIDAPI_KEY`, and optional `LOCAL_FINGERPRINT_INDEX` (with `FINGERPRINT_INDEX_PATH` accepted as a legacy alias). The shared audio contract is controlled by `INTERNAL_SAMPLE_RATE`, `INTERNAL_SAMPLE_WIDTH`, `MIN_AUDIO_SECONDS`, `MAX_AUDIO_SECONDS`, `MAX_UPLOAD_BYTES`, and `FFMPEG_TIMEOUT_SECONDS`. Matcher order is RapidAPI → AcoustID → AudD → local fingerprint index.

## Web UI
`python web/app.py` serves `/`, `/static/*`, `/api/match`, and `/api/status` from the same origin. CLI file mode accepts WAV/PCM files. Web uploads support WAV, MP3, M4A, AAC, OGG, FLAC, and WEBM; non-WAV web uploads require FFmpeg on `PATH` and are converted before decoding. The browser also supports microphone recording, manual stop, waveform visualization, loading/error/no-match states, light/dark theme persistence, and session-only recognition history.

Every input is downmixed to mono float32 samples in `[-1, 1]` and resampled to 44,100 Hz by default. Provider adapters receive temporary mono 16-bit PCM WAV files. Inputs shorter than 1 second, longer than 30 seconds, or larger than 10 MiB are rejected by default; all three limits are configurable.

## Testing
Run the Python tests and coverage locally:
```powershell
python -m pytest -q
python -m coverage run --branch --source=shazam_project,web,scripts -m pytest -q
python -m coverage report --fail-under=50 --show-missing
```
`tests/` covers FFT image creation, mocked provider flows, dispatcher fallback, web routes, and synthetic local fingerprint index matching.

GitHub Actions runs pytest on every push and pull request across Python 3.10, 3.11, and 3.12. A Python 3.12 coverage job enforces at least 50% total branch coverage across the Python packages and benchmark scripts and publishes `coverage.xml` as an artifact. Codecov integration is deferred to the later CI-hardening task because the current upload reports `Repository not found`; the README does not claim a successful Codecov upload.

For the real-world comparison, see [`evaluation/README.md`](evaluation/README.md). It records speaker-to-microphone clips at 4, 8, and 15 seconds, builds the local landmark-hash index from clean source tracks, and compares the local backend against all three provider backends.

## Limitations

Recognition is not guaranteed outside the happy path. The main failure modes are:

- **Background noise and recording quality:** speech, room echo, speaker distortion, very low volume, clipping, or music mixed with other sounds can hide the spectral peaks used by fingerprinting.
- **Catalog coverage:** a provider can only return tracks in its database, while the local matcher can only identify tracks present in its local fingerprint index. A `no_match` result does not prove that the audio is invalid.
- **Language and regional catalog differences:** the fingerprinting itself is not English-specific, but provider metadata and catalog coverage vary by language, region, release, and recording availability.
- **Live, cover, remix, and alternate versions:** crowd noise, changed instrumentation, tempo or pitch, medleys, and different arrangements may fail to match or may be returned as the closest studio recording rather than the exact performance.

The evaluation dataset is designed to measure these cases separately. Until that dataset is recorded and run through all configured backends, the README does not claim a general accuracy percentage.

## Production blockers for Prompt 4

This PR documents the shipped pipeline and does not redesign authentication or quotas. Before production deployment, Prompt 4 must address:

- The configured Origin/Referer path can bypass `INTERNAL_API_SECRET` for same-origin or allowlisted browser requests; the trust model and secret boundary need a deliberate production decision.
- Supabase quota reads and increments are not atomic, so concurrent requests can race past limits.
- Supabase failures currently fail open by returning zero usage and continuing recognition; production behavior must be fail-closed or visibly disable quota-protected recognition.

## Notes & Tips
- Record in a quiet space and keep the mic near the audio source.
- For AcoustID, install Chromaprint (`fpcalc`): macOS `brew install chromaprint`, Debian/Ubuntu `apt install libchromaprint-tools`.
- FFmpeg is required for non-WAV web uploads and is not required for WAV uploads.

## Contributing
Pull requests are welcome. For major changes, open an issue first.
Run `python -m pytest -q` and `python -m coverage report` before submitting.

***

## Example Output

```
Listen via microphone or load a file? (mic/file): mic

Recording for 8 seconds...
FFT diagnostic visualization saved to fft_output.png

Song:    Blinding Lights
Artist:  The Weeknd

[Album art opens in image viewer]
```

FFT spectrum for a sample clip:

![FFT spectrum output](docs/screenshots/fft-output.png)

This image is diagnostic output from `shazam_project.fft_analyze.analyze_audio`; the canonical browser page is served by `python web/app.py` at `/`.

***

## Web API Reference

| Endpoint       | Method | Description                                           |
|----------------|--------|-------------------------------------------------------|
| `/api/match`   | POST   | Upload an audio file for recognition. Returns JSON.  |
| `/api/status`  | GET    | Reports configured backends, ffmpeg, fpcalc status.  |

**Example — cURL:**
```bash
curl -X POST http://localhost:5000/api/match \
  -F "file=@song.wav"
```

**Example — Response:**
```json
{
  "status": "matched",
  "title": "Blinding Lights",
  "artist": "The Weeknd",
  "album": "After Hours",
  "image": "https://..."
}
```

Public `status` is one of: `matched` · `no_match` · `not_configured` · `invalid_audio` · `rate_limited` · `error`. Provider attempts may include safe `error_code` and diagnostic fields, but raw provider payloads, credentials, local paths, and stack traces are not public response data.

***

## Notes

- Record in a **quiet environment** for best accuracy
- CLI mic mode requires a working input device; the web UI uses browser microphone
- File mode (CLI) accepts WAV/PCM only; the web UI supports the documented formats and requires FFmpeg for non-WAV uploads.
- Windows, macOS, and Linux support has not been independently verified by this branch's evidence.

***

## Roadmap

- [x] Add CI — run pytest and coverage on every push and pull request
- [ ] CLI flags: `--mode`, `--duration`, `--file` for unattended/scripted use
- [ ] Local match history saved as JSON
- [ ] `--no-open-image` flag for headless environments
- [ ] Structured logging in `shazam_project/matcher.py` for easier debugging
- [x] Flask integration tests for the browser entry point, static assets, API status, and upload outcomes

***

## License

[MIT](LICENSE) — free to use and modify.
