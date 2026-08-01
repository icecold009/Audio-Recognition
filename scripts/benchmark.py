from __future__ import annotations

import argparse
import csv
import json
import statistics
import time
import unicodedata
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from shazam_project import matcher
from shazam_project.config import AppConfig, load_config
from shazam_project.recorder import load_audio_file

BACKENDS: dict[str, tuple[str, Callable[..., dict[str, Any]], str]] = {
    "rapidapi": ("RapidAPI/Shazam", matcher.match_audio_shazam, "rapidapi_key"),
    "acoustid": ("AcoustID", matcher.match_audio_acoustid, "acoustid_api_key"),
    "audd": ("AudD", matcher._match_audio_audd, "audd_api_token"),
    "local": ("Local constellation-hash", matcher.match_audio_local, "fingerprint_index_path"),
}


def _normalise(value: str | None) -> str:
    text = unicodedata.normalize("NFKD", value or "")
    text = "".join(char for char in text if not unicodedata.combining(char))
    return " ".join("".join(char if char.isalnum() else " " for char in text.lower()).split())


def _matches(actual: str | None, expected: str) -> bool:
    expected_values = [_normalise(item) for item in expected.split("|") if item.strip()]
    actual_value = _normalise(actual)
    return bool(actual_value and expected_values and actual_value in expected_values)


def _failure_reason(status: str, result: dict[str, Any]) -> str:
    if status == "not_configured":
        return "backend credentials are not configured"
    if status == "no_match":
        return "provider returned no match"
    if status == "error":
        return f"provider error: {result.get('error') or 'unspecified error'}"
    return "returned metadata did not match the manifest title and artist"


def _configured(config: AppConfig, attribute: str) -> bool:
    return bool(getattr(config, attribute, ""))


def _run_backend(
    backend: str,
    clip_path: Path,
    row: dict[str, str],
    config: AppConfig,
    timeout: int,
) -> dict[str, Any]:
    display_name, function, credential_attribute = BACKENDS[backend]
    base: dict[str, Any] = {
        "backend": backend,
        "backend_name": display_name,
        "clip_id": row["clip_id"],
        "clip_length_s": float(row["clip_length_s"]),
        "audio_path": row["audio_path"],
    }

    if not _configured(config, credential_attribute):
        base.update({"status": "not_configured", "correct": False})
        base["failure_reason"] = _failure_reason("not_configured", base)
        return base

    started = time.perf_counter()
    try:
        clip = load_audio_file(clip_path)
        result = function(clip, config, timeout=timeout)
        status = result.get("status", "error")
    except Exception as exc:
        result = {"status": "error", "error": str(exc)}
        status = "error"

    elapsed_ms = round((time.perf_counter() - started) * 1000, 2)
    title = result.get("title")
    artist = result.get("artist")
    correct = (
        status == "matched"
        and _matches(title, row["expected_title"])
        and _matches(artist, row["expected_artist"])
    )
    base.update(
        {
            "status": status,
            "correct": correct,
            "latency_ms": elapsed_ms,
            "returned_title": title or "",
            "returned_artist": artist or "",
            "returned_album": result.get("album") or "",
        }
    )
    if not correct:
        base["failure_reason"] = _failure_reason(status, result)
    return base


def _aggregate(records: list[dict[str, Any]], backend: str) -> dict[str, Any]:
    backend_records = [record for record in records if record["backend"] == backend]
    attempted = [record for record in backend_records if record["status"] != "not_configured"]
    correct = [record for record in attempted if record["correct"]]
    latencies = [record["latency_ms"] for record in attempted if "latency_ms" in record]

    by_length: dict[str, dict[str, Any]] = {}
    for length in sorted({record["clip_length_s"] for record in backend_records}):
        all_for_length = [record for record in backend_records if record["clip_length_s"] == length]
        subset = [record for record in attempted if record["clip_length_s"] == length]
        subset_correct = [record for record in subset if record["correct"]]
        by_length[str(length)] = {
            "total_clips": len(all_for_length),
            "attempted": len(subset),
            "correct": len(subset_correct),
            "accuracy": round(len(subset_correct) / len(subset), 4) if subset else None,
        }

    failures = [
        {
            "clip_id": record["clip_id"],
            "clip_length_s": record["clip_length_s"],
            "status": record["status"],
            "returned_title": record.get("returned_title", ""),
            "returned_artist": record.get("returned_artist", ""),
            "reason": record.get("failure_reason", "unknown failure"),
        }
        for record in backend_records
        if not record["correct"]
    ]
    return {
        "total_clips": len(backend_records),
        "attempted": len(attempted),
        "correct": len(correct),
        "accuracy": round(len(correct) / len(attempted), 4) if attempted else None,
        "no_match": sum(record["status"] == "no_match" for record in attempted),
        "errors": sum(record["status"] == "error" for record in attempted),
        "not_configured": sum(record["status"] == "not_configured" for record in backend_records),
        "latency_ms": {
            "mean": round(statistics.mean(latencies), 2) if latencies else None,
            "median": round(statistics.median(latencies), 2) if latencies else None,
            "p95": round(sorted(latencies)[max(0, int(len(latencies) * 0.95) - 1)], 2)
            if latencies
            else None,
        },
        "by_clip_length": by_length,
        "failures": failures,
    }


def run(manifest_path: Path, output_path: Path, timeout: int, env_path: Path) -> dict[str, Any]:
    config = load_config(env_path)
    with manifest_path.open(newline="", encoding="utf-8-sig") as handle:
        rows = list(csv.DictReader(handle))

    required = {"clip_id", "audio_path", "expected_title", "expected_artist", "clip_length_s"}
    missing = required - set(rows[0]) if rows else required
    if missing:
        raise ValueError(f"Manifest is missing required columns: {', '.join(sorted(missing))}")

    records: list[dict[str, Any]] = []
    for row in rows:
        clip_path = Path(row["audio_path"])
        if not clip_path.is_absolute():
            clip_path = (manifest_path.parent / clip_path).resolve()
        for backend in BACKENDS:
            if clip_path.exists():
                records.append(_run_backend(backend, clip_path, row, config, timeout))
            else:
                records.append(
                    {
                        "backend": backend,
                        "backend_name": BACKENDS[backend][0],
                        "clip_id": row["clip_id"],
                        "clip_length_s": float(row["clip_length_s"]),
                        "audio_path": row["audio_path"],
                        "status": "error",
                        "correct": False,
                        "failure_reason": "benchmark clip file is missing",
                    }
                )

    output = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "manifest": str(manifest_path),
        "timeout_seconds": timeout,
        "clip_count": len(rows),
        "backend_summary": {backend: _aggregate(records, backend) for backend in BACKENDS},
        "records": records,
    }
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2), encoding="utf-8")
    return output


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Run all configured music-recognition backends against a manifest."
    )
    parser.add_argument("--manifest", type=Path, required=True)
    parser.add_argument("--output", type=Path, default=Path("evaluation/results/benchmark.json"))
    parser.add_argument("--timeout", type=int, default=15)
    parser.add_argument("--env", type=Path, default=Path(".env"))
    args = parser.parse_args()
    run(args.manifest, args.output, args.timeout, args.env)
    print(f"Wrote benchmark results to {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
