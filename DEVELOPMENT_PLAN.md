# DIY Shazam Development Plan

This document is the implementation and operating plan for the repository. The current code files are placeholders, so this plan covers the full path from environment setup through audio capture, FFT analysis, AudD recognition, result display, and verification.

## 1. Project Goal

Build a terminal-based Python application that can:

1. Record audio from a microphone.
2. Load an existing audio file.
3. Analyze the audio with FFT and save a spectrum plot.
4. Send the audio to the AudD API for song recognition.
5. Display the matched song title, artist, and album art.

The repo should stay small, modular, and easy to run on Windows, macOS, and Linux.

## 2. Current Repository State

At the time of this plan, the following files exist but are empty:

- `main.py`
- `recorder.py`
- `fft_analyze.py`
- `matcher.py`
- `display.py`
- `requirements.txt`

The README describes the intended behavior, but the implementation still needs to be written.

## 3. Required Environment

### Python version

- Use Python 3.10 or newer.

### System requirements

- A working microphone for record mode.
- Internet access for the AudD API.
- A terminal capable of showing Unicode text.
- Optional image viewer support for album art.

### Runtime configuration

- Create a `.env` file at the repo root.
- Store the AudD token in `AUDD_API_TOKEN`.
- Do not commit secrets or generated audio artifacts.

## 4. Dependencies To Add

The `requirements.txt` file is empty and should be populated with the libraries needed for the app.

Recommended package set:

- `numpy`
- `scipy`
- `matplotlib`
- `sounddevice`
- `soundfile` if file loading or WAV handling needs it
- `requests`
- `python-dotenv`
- `Pillow`

If the implementation uses only built-in WAV support for file mode, `soundfile` may not be necessary.

## 5. Target File Responsibilities

### `main.py`

This should be the orchestration layer.

Responsibilities:

1. Prompt the user to choose microphone mode or file mode.
2. Collect the input audio path or record audio as needed.
3. Pass audio data through FFT analysis.
4. Pass the same audio clip to the recognition step.
5. Hand the final result to the display layer.
6. Handle top-level errors and keep the terminal output readable.

Expected structure:

- `main()` function.
- Input selection prompt.
- Sequential calls into the other modules.
- A final success or failure message.

### `recorder.py`

This should manage audio acquisition.

Responsibilities:

1. Record audio from the microphone for a fixed duration.
2. Load an audio file from disk.
3. Normalize output into one consistent in-memory format for downstream steps.
4. Validate sample rate, duration, and file existence.
5. Save or return the captured audio clip in a format the matcher and FFT analyzer can use.

Implementation notes:

- Support at least WAV files for the first version.
- Convert stereo input to mono if needed.
- Make it explicit when recording starts and ends.
- Return metadata such as sample rate and source type.

### `fft_analyze.py`

This should generate the frequency-spectrum analysis.

Responsibilities:

1. Accept raw audio samples and sample rate.
2. Compute the FFT.
3. Derive the magnitude spectrum.
4. Plot the spectrum with Matplotlib.
5. Save the plot to a predictable file, such as `fft_output.png`.

Implementation notes:

- Use a clear filename and overwrite it consistently.
- Ensure the plot labels are readable.
- Keep the function deterministic so the same input produces the same plot.

### `matcher.py`

This should perform the AudD API request and parse the response.

Responsibilities:

1. Read `AUDD_API_TOKEN` from the environment.
2. Upload the audio clip using the AudD recognition endpoint.
3. Handle request errors, timeouts, and non-200 responses.
4. Parse the returned JSON.
5. Return the relevant song metadata.

Implementation notes:

- Support a clear `no match` response.
- Keep API-specific details isolated in this file.
- Use a timeout so the app does not hang indefinitely.

### `display.py`

This should format the final result for the terminal and optionally show artwork.

Responsibilities:

1. Print the song title and artist in a readable format.
2. Display album art if a URL is available.
3. Handle image download failures gracefully.
4. Keep the terminal output concise and consistent.

Implementation notes:

- If image display fails, still print the text result.
- Avoid breaking the main flow because artwork cannot be loaded.

## 6. End-to-End Workflow

The application should follow this sequence:

1. User runs `python main.py`.
2. The app asks whether to use microphone input or an audio file.
3. The app records or loads audio.
4. The audio is normalized into a consistent sample buffer.
5. FFT analysis runs and writes `fft_output.png`.
6. The audio is sent to AudD.
7. The app prints the match result.
8. If artwork is available, it is shown separately from the text output.

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

### Step 4: Add AudD matching

1. Implement environment-variable loading in `matcher.py`.
2. Send the audio clip to the AudD API.
3. Parse the response into a structured result object or dictionary.
4. Handle failures cleanly.

### Step 5: Add display logic

1. Implement formatted terminal output in `display.py`.
2. Add album-art download and display support.
3. Preserve result printing even when image display fails.

### Step 6: Wire everything in `main.py`

1. Connect input selection to audio capture.
2. Run FFT before recognition.
3. Pass recognition results to the display function.
4. Add top-level exception handling.

### Step 7: Validate the app

1. Test microphone mode.
2. Test file mode with a known WAV sample.
3. Test no-match behavior.
4. Test missing token behavior.
5. Test bad file input behavior.
6. Confirm the FFT image is generated each run.

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

## 9. Testing Checklist

Minimum checks to run before considering the app usable:

1. `main.py` launches without import errors.
2. Microphone mode can capture a clip.
3. File mode can load a WAV file.
4. FFT analysis writes `fft_output.png`.
5. AudD response parsing works for success and no-match payloads.
6. Missing-token handling works.
7. Invalid-input handling works.
8. Album art failure does not break the program.

## 10. Suggested Output Standards

Keep terminal output consistent:

1. Announce the chosen input mode.
2. Show when recording or loading starts.
3. Confirm when FFT analysis completes.
4. Show the recognized song title and artist on separate lines.
5. Show a final success or failure state.

## 11. Future Improvements

After the first working version, consider:

1. Adding unit tests for each module.
2. Supporting more audio formats.
3. Adding command-line arguments for duration and input path.
4. Saving recognition history to a local file.
5. Adding a small CLI help message.

## 12. Done Criteria

The project is complete when:

1. A user can run the app from a clean install.
2. Both mic and file workflows work end to end.
3. FFT output is saved reliably.
4. AudD results are displayed clearly.
5. Failure cases are handled without crashing.
