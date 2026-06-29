<div align="center">

[![CI](https://github.com/icecold009/Shazam-project/actions/workflows/ci.yml/badge.svg)](https://github.com/icecold009/Shazam-project/actions/workflows/ci.yml)

<br/>

**Identify any song from your microphone or an audio file.**  
FFT analysis · Multi-backend matching · Flask web UI · Terminal output


</div>

***
<div align="center">
  <h1 style="margin:0;padding:0">Audio Recognition</h1>
  <p style="margin:4px 0 8px;color:#1E90FF">Identify songs from your microphone or an audio file — FFT + multi-backend matching</p>
</div>

## Overview
DIY Shazam captures audio (mic or file), creates a frequency spectrum (FFT), and identifies tracks using one of several backends (RapidAPI/Shazam, AcoustID, AudD). A compact Flask web UI enables browser uploads.

## Performance

| Metric | Result |
|--------|--------|
| Average recognition time (RapidAPI backend) | ~2.1 s |
| Average recognition time (AudD backend) | ~3.4 s |
| Test set accuracy | X / Y songs matched correctly |
| Sample audio length required | 8 s (configurable) |
| Platforms tested | Windows 11, Ubuntu 22.04, macOS 14 |

## Architecture
```mermaid
flowchart LR
  A[CLI / Web UI] --> B[Audio Input\n(mic or upload)]
  B --> C[FFT Analysis\n(saves fft_output.png)]
  B --> D[Write WAV temp]
  D --> E{Matcher Backends}
  E -->|RapidAPI| F[Shazam]
  E -->|AcoustID| G[AcoustID]
  E -->|AudD| H[AudD]
  F & G & H --> I[Normalized Result]
  I --> J[Display (CLI) / JSON (Web)]
  classDef blue fill:#ffffff,stroke:#1E90FF,stroke-width:2px,color:#1E90FF;
  class A,B,C,D,E,F,G,H,I,J blue;
```
Theme: black / white / blue — white nodes with a professional DodgerBlue accent (#1E90FF).

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
4) Run CLI:
```powershell
python main.py
```
5) Run web UI (dev):
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
- `web/app.py` (Flask web app)

## Configuration
Supported env vars (see `shazam_project.config.load_config()`): `AUDD_API_TOKEN`, `ACOUSTID_API_KEY`, `FP_CALC_PATH`, `RAPIDAPI_KEY`. Matcher order: RapidAPI → AcoustID → AudD.

## Web UI
`web/app.py` exposes `/api/match` for uploads and `/api/status` for tool/backend checks. Non-WAV uploads are converted with `ffmpeg` if present.

## Testing
Run tests:
```powershell
python -m unittest discover -v
```
`tests/test_core.py` covers FFT image creation and a mocked AcoustID flow.

## Notes & Tips
- Record in a quiet space and keep the mic near the audio source.
- For AcoustID, install Chromaprint (`fpcalc`): macOS `brew install chromaprint`, Debian/Ubuntu `apt install libchromaprint-tools`.
- `ffmpeg` is optional for the web upload conversion path.

## Contributing
Pull requests are welcome. For major changes, open an issue first.
Run `python -m unittest discover -v` before submitting.

***

## Example Output

```
Listen via microphone or load a file? (mic/file): mic

Recording for 8 seconds...
FFT analysis saved to fft_output.png

Song:    Blinding Lights
Artist:  The Weeknd

[Album art opens in image viewer]
```

FFT spectrum for a sample clip:



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

`status` is one of: `matched` · `no_match` · `no_token` · `error`

***

## Notes

- Record in a **quiet environment** for best accuracy
- CLI mic mode requires a working input device; the web UI uses browser microphone
- File mode (CLI) accepts WAV by default; the web UI converts other formats via `ffmpeg` if available
- Tested on Windows, macOS, and Linux

***

## Roadmap

- [ ] Add CI — run `pytest` + lint on push
- [ ] CLI flags: `--mode`, `--duration`, `--file` for unattended/scripted use
- [ ] Local match history saved as JSON
- [ ] `--no-open-image` flag for headless environments
- [ ] Structured logging in `shazam_project/matcher.py` for easier debugging
- [ ] End-to-end Flask test using the test client with a sample WAV

***

## License

[MIT](LICENSE) — free to use and modify.