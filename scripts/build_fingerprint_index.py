from __future__ import annotations

import argparse
import csv
from pathlib import Path

from shazam_project.fingerprint import build_index


def main() -> int:
    parser = argparse.ArgumentParser(description="Build a local constellation-hash fingerprint index.")
    parser.add_argument("--sources", type=Path, required=True, help="CSV with track_id/source_id, source_audio_path, title, artist")
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/fingerprint-index.json"))
    args = parser.parse_args()

    with args.sources.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))
    if not rows:
        raise ValueError("The source manifest is empty")

    tracks: list[dict[str, str]] = []
    for row in rows:
        audio_path = Path(row["source_audio_path"])
        if not audio_path.is_absolute():
            audio_path = (args.sources.parent / audio_path).resolve()
        tracks.append(
            {
                "track_id": row.get("track_id") or row.get("source_id", ""),
                "audio_path": str(audio_path),
                "title": row.get("title", ""),
                "artist": row.get("artist", ""),
                "album": row.get("album", ""),
                "genre": row.get("genre", ""),
                "era": row.get("era", ""),
            }
        )

    output = build_index(tracks, args.output)
    print(f"Indexed {len(tracks)} tracks into {output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
