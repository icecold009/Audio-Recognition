from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from scripts.benchmark import BACKENDS, render_markdown

START_MARKER = "<!-- BENCHMARK_RESULTS:START -->"
END_MARKER = "<!-- BENCHMARK_RESULTS:END -->"


def validate_complete_results(results: dict[str, Any]) -> None:
    metadata = results.get("metadata")
    summaries = results.get("backend_summary")
    clip_count = results.get("clip_count")
    if (
        not isinstance(metadata, dict)
        or not isinstance(summaries, dict)
        or not isinstance(clip_count, int)
    ):
        raise ValueError("Benchmark results are incomplete: required sections are missing.")
    if not metadata.get("complete"):
        raise ValueError("Benchmark results are incomplete; README was not changed.")
    if not metadata.get("network_region") or not metadata.get("provider_plan"):
        raise ValueError("Benchmark results are incomplete: operator metadata is missing.")
    if set(summaries) != set(BACKENDS):
        raise ValueError("Benchmark results are incomplete: all backends are required.")
    for backend in BACKENDS:
        summary = summaries[backend]
        if summary.get("not_configured") or summary.get("attempted") != clip_count:
            raise ValueError(
                f"Benchmark results are incomplete for {backend}; README was not changed."
            )


def update_readme(readme_path: Path, results: dict[str, Any]) -> None:
    validate_complete_results(results)
    text = readme_path.read_text(encoding="utf-8")
    if START_MARKER not in text or END_MARKER not in text:
        raise ValueError("README benchmark markers are missing; README was not changed.")
    start = text.index(START_MARKER) + len(START_MARKER)
    end = text.index(END_MARKER, start)
    replacement = "\n\n" + render_markdown(results).rstrip() + "\n\n"
    readme_path.write_text(text[:start] + replacement + text[end:], encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Import complete benchmark results into readme.md."
    )
    parser.add_argument("--results", type=Path, required=True)
    parser.add_argument("--readme", type=Path, default=Path("readme.md"))
    args = parser.parse_args()
    try:
        results = json.loads(args.results.read_text(encoding="utf-8"))
        update_readme(args.readme, results)
    except (OSError, UnicodeError, json.JSONDecodeError, ValueError) as exc:
        raise SystemExit(str(exc)) from exc
    print(f"Updated benchmark results in {args.readme}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
