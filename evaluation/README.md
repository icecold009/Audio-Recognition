# Real-world recognition benchmark

This benchmark is intentionally based on speaker-to-microphone recordings. Clean source files are used only as playback material; the clips sent to the recognition providers are the microphone captures.

## Target design

- 30 source tracks, producing 90 clips: one 4-second, one 8-second, and one 15-second clip per track.
- At least 10 genres, with representation across multiple decades where the licensed/source catalog permits it.
- Every row includes title, artist, genre, era, source provenance, recording condition, and clip length.
- Use at least three recording conditions across the source set: near speaker, normal room distance, and background-noise/room ambience.
- Keep source audio and captured clips outside Git. Store only manifests, scripts, aggregate results, and failure explanations in the repository.
- Do not call a backend result correct unless both normalized title and artist match the manifest ground truth. Use `|` in a manifest field only for documented aliases.

## Prepare source tracks

Create `evaluation/sources.csv` from user-owned or legally reusable source audio. Required columns:

```csv
source_id,source_audio_path,title,artist,genre,era,condition
track-001,C:\\path\\to\\track.wav,Example Song,Example Artist,pop,2010s,speaker_mic_room
```

The benchmark should retain a source/license note for every track. Do not add copyrighted audio to this repository.

## Record the realistic clips

List the available devices first:

```powershell
.\\.venv\\Scripts\\python.exe -c "import sounddevice as sd; print(sd.query_devices())"
```

Then record 4/8/15-second slices from a 15-second speaker playback for every source:

```powershell
.\\.venv\\Scripts\\python.exe scripts/record_benchmark.py `
  --sources evaluation/sources.csv `
  --input-device 1 `
  --output-device 4
```

Use `--yes` only after confirming the device indices and physical room setup. The script writes `evaluation/manifest.csv` and `evaluation/clips/`.

## Run all backends

```powershell
.\\.venv\\Scripts\\python.exe scripts/benchmark.py `
  --manifest evaluation/manifest.csv `
  --output evaluation/results/benchmark.json
```

The runner calls RapidAPI/Shazam, AcoustID, and AudD independently. It reports configured coverage rather than treating a missing credential as a successful zero score.

The JSON output contains:

- overall attempted/correct/accuracy per backend;
- accuracy by 4s, 8s, and 15s clip length;
- no-match, error, and latency summaries;
- one-line failure explanations with returned metadata.

## Required report

Before updating the README, verify that all three backends were configured and attempted for every clip. Report the exact denominator, not only a percentage. Include the credentialed run date, source/condition counts, and a short explanation for every failure.
