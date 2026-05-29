# DIY Shazam Development Plan

This document describes the current implementation and the short-term roadmap for the repository. The codebase already implements CLI and web flows, FFT plotting, three matching backends (RapidAPI/Shazam, AcoustID, AudD), and basic tests. The plan below documents what exists now and what to do next.

## 1. Project Goal

Build a terminal-based Python application that can:

1. Record audio from a microphone.
2. Load an existing audio file.
3. Analyze the audio with FFT and save a spectrum plot.
4. Send the audio to the AudD API for song recognition.
5. Display the matched song title, artist, and album art.

The repo should stay small, modular, and easy to run on Windows, macOS, and Linux.

## 2. Current Repository State

The repository already contains working implementations for the main features:

- `main.py` — CLI entrypoint that orchestrates config loading, audio capture (mic/file), FFT analysis, and matching.
- `recorder.py` — WAV file loader and microphone recorder (uses `sounddevice` when available). Returns a unified `AudioClip` dataclass.
- `fft_analyze.py` — Computes FFT with NumPy and writes a frequency-spectrum PNG using Matplotlib (Agg backend).
- `matcher.py` — Multi-backend matcher: prefers RapidAPI (Shazam) when `RAPIDAPI_KEY` is set, supports AcoustID via local `fpcalc`, and falls back to AudD when `AUDD_API_TOKEN` is configured.
- `display.py` — Prints formatted results and attempts to download/show album art with Pillow.
- `web/app.py` — Minimal Flask web UI exposing `/api/match` and `/api/status`, handles uploads and optional ffmpeg conversion.
- `tests/test_core.py` — Unit tests covering FFT file creation and a mocked AcoustID flow.

The README and code are in sync with the implemented features.

## 3. Required Environment

### Python

- Python 3.10+ is recommended (code uses modern typing and dataclasses).

### System requirements

- Microphone for CLI mic mode (or browser microphone for web UI).
- `ffmpeg` is optional but recommended for the web upload conversion path.
- `fpcalc` (Chromaprint) is required only if you want AcoustID fingerprinting.

### Runtime configuration

- Place tokens/config in a `.env` at the repo root. Keys supported by `config.load_config()`:
	- `AUDD_API_TOKEN` (AudD)
	- `ACOUSTID_API_KEY` (AcoustID)
	- `FP_CALC_PATH` (optional full path to `fpcalc`)
	- `RAPIDAPI_KEY` (RapidAPI/Shazam)

The app will try RapidAPI → AcoustID → AudD in that order, depending on available configuration.

## 4. Dependencies

Populate `requirements.txt` with the runtime libraries used by the code:

- `numpy`
- `matplotlib` (plotting; code uses Agg backend for headless use)
- `requests` (HTTP calls)
- `python-dotenv` (env loading)
- `pillow` (image handling)
- `sounddevice` (optional, required for CLI mic recording)
- `flask` (web UI)

Optional developer/system dependencies:

- `ffmpeg` (external binary, used by the web app to convert uploads when necessary)
- `fpcalc` / Chromaprint (external binary for AcoustID fingerprinting)

## 5. Target File Responsibilities

### `main.py` (existing)

`main.py` implements the orchestration described above. It:

- Loads config via `config.load_config()` and reports missing tokens/backends.
- Accepts `mic` or `file` input, uses `recorder.record_microphone()` or `recorder.load_audio_file()`.
- Runs `fft_analyze.analyze_audio()` and writes the output PNG.
- Calls `matcher.match_audio()` and renders results via `display.show_result()`.

The CLI already includes error handling for input and analysis failures.

### `recorder.py` (existing)

Implemented responsibilities:

- Loads WAV files using the standard `wave` module (supports 8/16/32-bit PCM conversions).
- Records from the microphone with `sounddevice` when available, returning a float32 mono `AudioClip`.
- Normalizes stereo → mono by averaging channels and returns `AudioClip(samples, sample_rate, source, path)`.

Notes:

- File-mode currently accepts only WAV files; the web UI attempts ffmpeg conversion for other formats before loading.

### `fft_analyze.py` (existing)

Implemented responsibilities:

- Computes real FFT with NumPy and saves a labeled PNG using Matplotlib (Agg backend).
- Validates non-empty samples and positive sample rate.

Output:

- Default file: `fft_output.png` (configurable via `AppConfig.fft_output_path`).

### `matcher.py` (existing)

Implemented responsibilities and behavior:

- Provides three backends and chooses the first available in this order: RapidAPI (Shazam) → AcoustID → AudD.
- Writes a temporary 16-bit WAV from the `AudioClip` for upload/fingerprinting.
- Calls external `fpcalc` for AcoustID if configured (or uses `FP_CALC_PATH`).
- Returns normalized result dictionaries: `status` is one of `matched`, `no_match`, `no_token`, or `error`. When matched, keys include `title`, `artist`, `album`, and optional `image` URL.

Notes:

- The RapidAPI path encodes audio to base64 and posts to the Shazam RapidAPI endpoint.
- The AudD path posts a file to `https://api.audd.io/` and extracts album art from multiple potential fields.

### `display.py` (existing)

Implemented responsibilities:

- Prints song metadata to the terminal with emoji markers.
- If an image URL is present, attempts to download it and show it with Pillow (`Image.show()`), but failures are logged to stdout and do not halt the program.

## 6. End-to-End Workflow (current)

CLI:

1. `python main.py` → load `.env` → report missing tokens/backends.
2. Choose `mic` or `file`.
3. Capture or load audio into `AudioClip`.
4. Run `fft_analyze.analyze_audio()` → write PNG.
5. Run `matcher.match_audio()` → choose backend according to config.
6. Display with `display.show_result()`.

Web UI (`web/app.py`):

1. POST a file to `/api/match` (browser or cURL).
2. Server optionally converts non-WAV uploads using `ffmpeg` (if available).
3. Loads a WAV and runs the same `matcher.match_audio()` code path.
4. `/api/status` reports configuration bits (fpcalc, ffmpeg, tokens).

## 7. Implementation Procedure

Follow this order to avoid rework.

### Step 1: Populate dependencies

1. Edit `requirements.txt` with the packages listed above.
2. Install the dependencies in a clean environment.
3. Confirm imports resolve before coding the app logic.

### Step 2: Build audio input first

1. Implement microphone recording in `recorder.py`.
2. Implement audio file loading in the same module.
3. Make both return the same data shape.
4. Validate that the app can acquire one clip from each input path.

### Step 3: Add FFT analysis

1. Implement the FFT function in `fft_analyze.py`.
2. Save the output plot to `fft_output.png`.
3. Verify the plot is created for both mic and file inputs.

## 7. Testing & Validation (current)

- Unit tests exist in `tests/test_core.py` and cover FFT image creation and a mocked AcoustID fingerprint flow.
- Recommended additional tests:
	- Mock RapidAPI and AudD responses to assert normalized result shapes.
	- Test `recorder.record_microphone()` behavior with a monkeypatched `sounddevice` object (CI skip when device missing).
	- End-to-end integration test for the Flask `/api/match` route using the Flask test client.

## 8. Short-term Roadmap (recommended)

1. Populate `requirements.txt` with the packages listed in section 4.
2. Add CI that runs `pytest` or `python -m unittest` and lints imports.
3. Add a small `.env.example` file documenting supported keys (if not already present).
4. Add CLI arguments (optional) to `main.py` for `--mode`, `--duration`, and `--file` to enable non-interactive usage.
5. Improve error logging (structured logs) in `matcher.py` for easier debugging of external errors.
6. Add a small e2e test for the web API using an uploaded sample clip.

## 8. Operational Procedures

### First-time setup

1. Clone the repository.
2. Create and activate a Python virtual environment.
3. Install dependencies from `requirements.txt`.
4. Add `AUDD_API_TOKEN` to `.env`.
5. Run `python main.py`.

### Microphone workflow

1. Choose microphone mode.
2. Speak or play audio into the microphone.
3. Wait for the capture duration to complete.
4. Review the FFT plot output.
5. Review the recognition result.

### Audio file workflow

1. Choose file mode.
2. Provide a valid audio file path.
3. Confirm the file is readable and supported.
4. Review the FFT plot output.
5. Review the recognition result.

### Failure handling

1. If the API token is missing, stop early and explain how to add it.
2. If the audio device is unavailable, show a microphone error.
3. If the file is invalid, explain the expected format.
4. If AudD returns no match, print a clear no-match status.
5. If album art cannot be loaded, keep the song result visible.


## 9. Quick Run Instructions

CLI:

```powershell
python main.py
```

Web UI (dev):

```powershell
python web/app.py
# then open http://127.0.0.1:5000
```

Run tests:

```powershell
python -m unittest discover -v
```

## 10. Suggested Output Standards

Keep terminal output consistent:

1. Announce the chosen input mode.
2. Show when recording or loading starts.
3. Confirm when FFT analysis completes.
4. Show the recognized song title and artist on separate lines.
5. Show a final success or failure state.

## 10. Future Improvements

- Add CI and automated tests.
- Add a lightweight history/log feature (JSON) to save matches locally.
- Add CLI flags for unattended runs and a `--no-open-image` option.
- Allow file-mode imports beyond WAV via server-side ffmpeg conversion (already attempted in web path).

## 11. Done Criteria

- CLI and web flows run without import errors.
- FFT output is generated for both mic and file inputs.
- Matching returns normalized structured results and the display layer renders them without crashing.

---

If you'd like, I can also:

- Open a patch to populate `requirements.txt` with the recommended packages.
- Add a `.env.example` file and a short CI workflow to run the tests.

