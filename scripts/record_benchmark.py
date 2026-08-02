from __future__ import annotations

import argparse
import csv
import math
import subprocess
import sys
import tempfile
from pathlib import Path

import numpy as np
import soundfile as sf

try:
    import sounddevice as sd
except (ImportError, OSError):  # pragma: no cover - depends on host PortAudio
    sd = None

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.evaluation import (
    ManifestValidationError,
    load_clip_manifest,
    load_source_manifest,
    relative_manifest_path,
    resolve_manifest_path,
)

CLIP_LENGTHS = (4, 8, 15)
SAMPLE_RATE = 44100
CLIP_COLUMNS = (
    "source_id",
    "clip_id",
    "audio_path",
    "expected_title",
    "expected_artist",
    "genre",
    "era",
    "recording_condition",
    "provenance_or_license_note",
    "clip_length_s",
)


def _decode_source(source_path: Path) -> tuple[np.ndarray, int]:
    if source_path.suffix.lower() in {".wav", ".flac", ".ogg"}:
        samples, sample_rate = sf.read(source_path, dtype="float32", always_2d=False)
    else:
        with tempfile.NamedTemporaryFile(suffix=".wav", delete=False) as converted:
            converted_path = Path(converted.name)
        try:
            subprocess.run(
                [
                    "ffmpeg",
                    "-nostdin",
                    "-y",
                    "-i",
                    str(source_path),
                    "-ar",
                    str(SAMPLE_RATE),
                    "-ac",
                    "1",
                    str(converted_path),
                ],
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


def _clip_path(output_dir: Path, source_id: str, length: int) -> Path:
    return output_dir / f"{source_id}_{length}s.wav"


def _verified_clip(path: Path, length: int) -> bool:
    """Treat only a readable clip with enough frames as resumable state."""
    try:
        info = sf.info(path)
        return bool(info.frames >= math.ceil(length * info.samplerate) and info.channels >= 1)
    except (OSError, RuntimeError, ValueError):
        return False


def _clip_row(
    source: dict[str, str],
    path: Path,
    length: int,
    manifest_path: Path,
) -> dict[str, str]:
    row = {
        "source_id": source["source_id"],
        "clip_id": f"{source['source_id']}_{length}s",
        "audio_path": relative_manifest_path(manifest_path, path),
        "expected_title": source["title"],
        "expected_artist": source["artist"],
        "genre": source["genre"],
        "era": source["era"],
        "recording_condition": source["recording_condition"],
        "provenance_or_license_note": source["provenance_or_license_note"],
        "clip_length_s": str(length),
    }
    for key, value in source.items():
        if key.endswith("_id") and key not in row and value:
            row[key] = value
    return row


def _record_source(
    source: dict[str, str],
    output_dir: Path,
    input_device: int | str,
    output_device: int | str,
    pending_lengths: list[int] | None = None,
    manifest_path: Path | None = None,
) -> list[dict[str, str]]:
    manifest_path = manifest_path or output_dir / "manifest.csv"
    global sd
    if sd is None:
        try:
            import sounddevice as sd
        except (ImportError, OSError) as exc:  # pragma: no cover - host dependency
            raise RuntimeError("Microphone recording requires PortAudio and sounddevice.") from exc
    if pending_lengths is None:
        pending_lengths = [
            length
            for length in CLIP_LENGTHS
            if not _verified_clip(_clip_path(output_dir, source["source_id"], length), length)
        ]
    if not pending_lengths:
        return []

    source_path = Path(
        source.get("_resolved_source_path")
        or resolve_manifest_path(manifest_path, source["source_audio_path"])
    )
    samples, sample_rate = _decode_source(source_path)
    target_samples = int(15 * sample_rate)
    if len(samples) < target_samples:
        raise ValueError("A source track must contain at least 15 seconds of audio.")

    playback = samples[:target_samples]
    print(f"Playing and recording {source['source_id']} ({source['title']} — {source['artist']})")
    try:
        captured = sd.playrec(
            playback,
            samplerate=sample_rate,
            channels=1,
            dtype="float32",
            device=(input_device, output_device),
            blocking=True,
        )
    finally:
        try:
            sd.stop()
        except Exception:
            pass
    captured = np.asarray(captured, dtype=np.float32).reshape(-1)

    rows: list[dict[str, str]] = []
    for length in pending_lengths:
        path = _clip_path(output_dir, source["source_id"], length)
        sf.write(path, captured[: int(length * sample_rate)], sample_rate, subtype="PCM_16")
        rows.append(_clip_row(source, path, length, manifest_path))
    return rows


def _write_manifest(path: Path, rows: list[dict[str, str]]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    extra_columns = sorted(
        {key for row in rows for key in row if key.endswith("_id") and key not in CLIP_COLUMNS}
    )
    fieldnames = list(CLIP_COLUMNS) + extra_columns
    with path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def _load_existing_rows(path: Path) -> dict[str, dict[str, str]]:
    if not path.exists():
        return {}
    try:
        rows = load_clip_manifest(path, require_audio=False)
    except ManifestValidationError as exc:
        raise ManifestValidationError(
            "The existing clip manifest is invalid; repair it before resuming."
        ) from exc
    return {row["clip_id"]: row for row in rows}


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Record resumable 4/8/15-second speaker-to-microphone benchmark clips."
    )
    parser.add_argument(
        "--sources",
        type=Path,
        required=True,
        help="CSV with source_id,source_audio_path,title,artist,genre,era,recording_condition,provenance_or_license_note",
    )
    parser.add_argument("--output-dir", type=Path, default=Path("evaluation/clips"))
    parser.add_argument("--manifest", type=Path, default=Path("evaluation/manifest.csv"))
    parser.add_argument(
        "--input-device", required=True, help="sounddevice input device index or name"
    )
    parser.add_argument(
        "--output-device", required=True, help="sounddevice output device index or name"
    )
    parser.add_argument("--yes", action="store_true", help="do not pause before each recording")
    parser.add_argument(
        "--resume",
        action="store_true",
        default=True,
        help="preserve readable existing clips and record only missing/invalid clips (default)",
    )
    args = parser.parse_args()

    input_device: int | str = (
        int(args.input_device) if args.input_device.isdigit() else args.input_device
    )
    output_device: int | str = (
        int(args.output_device) if args.output_device.isdigit() else args.output_device
    )
    args.output_dir.mkdir(parents=True, exist_ok=True)
    sources = [
        {
            **source,
            "_resolved_source_path": str(
                resolve_manifest_path(args.sources, source["source_audio_path"])
            ),
        }
        for source in load_source_manifest(args.sources, require_audio=True)
    ]
    existing = _load_existing_rows(args.manifest) if args.resume else {}

    for source in sources:
        pending = [
            length
            for length in CLIP_LENGTHS
            if not _verified_clip(_clip_path(args.output_dir, source["source_id"], length), length)
        ]
        if not pending:
            print(f"Skipping {source['source_id']}: all clips are already verified.")
        else:
            if not args.yes:
                input(
                    f"Press Enter when the room and microphone are ready for {source['source_id']}..."
                )
            for row in _record_source(
                source,
                args.output_dir,
                input_device,
                output_device,
                pending_lengths=pending,
                manifest_path=args.manifest,
            ):
                existing[row["clip_id"]] = row

        ordered_rows = []
        for current_source in sources:
            for length in CLIP_LENGTHS:
                clip = _clip_path(args.output_dir, current_source["source_id"], length)
                if _verified_clip(clip, length):
                    ordered_rows.append(_clip_row(current_source, clip, length, args.manifest))
        _write_manifest(args.manifest, ordered_rows)

    print(f"Verified {len(_load_existing_rows(args.manifest))} clips in the benchmark manifest.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
