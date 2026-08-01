from __future__ import annotations

import argparse
import csv
from pathlib import Path
import subprocess
import tempfile

import numpy as np
import sounddevice as sd
import soundfile as sf


CLIP_LENGTHS = (4, 8, 15)
SAMPLE_RATE = 44100


def _decode_source(source_path: Path) -> tuple[np.ndarray, int]:
    if source_path.suffix.lower() in {".wav", ".flac", ".ogg"}:
        samples, sample_rate = sf.read(source_path, dtype="float32", always_2d=False)
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as converted:
            converted_path = Path(converted.name)
        try:
            subprocess.run(
                ["ffmpeg", "-y", "-i", str(source_path), "-ar", str(SAMPLE_RATE), "-ac", "1", str(converted_path)],
                check=True,
                capture_output=True,
                timeout=30,
            )
            samples, sample_rate = sf.read(converted_path, dtype="float32", always_2d=False)
        finally:
            converted_path.unlink(missing_ok=True)

    array = np.asarray(samples, dtype=np.float32)
    if array.ndim == 2:
        array = array.mean(axis=1)
    return array.reshape(-1), int(sample_rate)


def _record_source(source: dict[str, str], output_dir: Path, input_device: int | str, output_device: int | str) -> list[dict[str, str]]:
    source_path = Path(source["source_audio_path"])
    samples, sample_rate = _decode_source(source_path)
    target_samples = int(15 * sample_rate)
    if len(samples) < target_samples:
        raise ValueError(f"{source_path} is shorter than the required 15 seconds")

    playback = samples[:target_samples]
    print(f"Playing and recording {source['source_id']} ({source['title']} — {source['artist']})")
    captured = sd.playrec(
        playback,
        samplerate=sample_rate,
        channels=1,
        dtype="float32",
        device=(input_device, output_device),
        blocking=True,
    )
    captured = np.asarray(captured, dtype=np.float32).reshape(-1)

    rows: list[dict[str, str]] = []
    for length in CLIP_LENGTHS:
        clip_id = f"{source['source_id']}_{length}s"
        path = output_dir / f"{clip_id}.wav"
        sf.write(path, captured[: int(length * sample_rate)], sample_rate, subtype="PCM_16")
        rows.append(
            {
                "clip_id": clip_id,
                "audio_path": str(path.resolve()),
                "expected_title": source["title"],
                "expected_artist": source["artist"],
                "genre": source.get("genre", ""),
                "era": source.get("era", ""),
                "condition": source.get("condition", "speaker_mic"),
                "clip_length_s": str(length),
            }
        )
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description="Record 4/8/15-second speaker-to-microphone benchmark clips.")
    parser.add_argument("--sources", type=Path, required=True, help="CSV with source_id,source_audio_path,title,artist,genre,era,condition")
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/clips"))
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/manifest.csv"))
    parser.add_argument("--input-device", required=True, help="sounddevice input device index or name")
    parser.add_argument("--output-device", required=True, help="sounddevice output device index or name")
    parser.add_argument("--yes", action="store_true", help="do not pause before each recording")
    args = parser.parse_args()

    input_device: int | str = int(args.input_device) if args.input_device.isdigit() else args.input_device
    output_device: int | str = int(args.output_device) if args.output_device.isdigit() else args.output_device
    args.output_dir.mkdir(parents=True, exist_ok=True)

    with args.sources.open(newline="", encoding="utf-8-sig") as handle:
        sources = list(csv.DictReader(handle))
    if not sources:
        raise ValueError("The source manifest is empty")

    rows: list[dict[str, str]] = []
    for source in sources:
        if not args.yes:
            input(f"Press Enter when the room and microphone are ready for {source['source_id']}...")
        rows.extend(_record_source(source, args.output_dir, input_device, output_device))

    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    with args.manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    print(f"Recorded {len(rows)} clips to {args.output_dir}")
    print(f"Wrote benchmark manifest to {args.manifest}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
