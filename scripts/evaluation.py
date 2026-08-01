from __future__ import annotations

import csv
import re
from pathlib import Path

SOURCE_REQUIRED_COLUMNS = (
    "source_id",
    "source_audio_path",
    "title",
    "artist",
    "genre",
    "era",
    "recording_condition",
    "provenance_or_license_note",
)
CLIP_REQUIRED_COLUMNS = (
    "source_id",
    "clip_id",
    "audio_path",
    "expected_title",
    "expected_artist",
    "genre",
    "era",
    "recording_condition",
    "clip_length_s",
)
SOURCE_ID_PATTERN = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._-]*$")


class ManifestValidationError(ValueError):
    """Raised when an evaluation manifest cannot support a reproducible run."""


def _read_rows(path: Path) -> tuple[list[str], list[dict[str, str]]]:
    try:
        with path.open(newline="", encoding="utf-8-sig") as handle:
            reader = csv.DictReader(handle)
            headers = [header.strip() for header in (reader.fieldnames or []) if header]
            rows = [
                {str(key).strip(): (value or "").strip() for key, value in row.items() if key}
                for row in reader
            ]
    except OSError as exc:
        raise ManifestValidationError("Could not read the evaluation manifest.") from exc
    return headers, rows


def _require_columns(
    headers: list[str], required: tuple[str, ...], aliases: dict[str, str]
) -> None:
    missing = []
    for column in required:
        if column in headers:
            continue
        if any(alias in headers for alias, canonical in aliases.items() if canonical == column):
            continue
        missing.append(column)
    if missing:
        raise ManifestValidationError(
            "Manifest is missing required columns: " + ", ".join(sorted(missing))
        )


def _canonicalize_row(row: dict[str, str]) -> dict[str, str]:
    normalized = dict(row)
    if not normalized.get("recording_condition"):
        normalized["recording_condition"] = normalized.get("condition", "").strip()
    if not normalized.get("provenance_or_license_note"):
        normalized["provenance_or_license_note"] = (
            normalized.get("provenance", "").strip() or normalized.get("license_note", "").strip()
        )
    return normalized


def _validate_source_identity(rows: list[dict[str, str]]) -> None:
    seen: set[str] = set()
    for row_number, raw_row in enumerate(rows, start=2):
        row = _canonicalize_row(raw_row)
        source_id = row.get("source_id", "").strip()
        if not source_id or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ManifestValidationError(f"Row {row_number} has an invalid stable source_id.")
        if source_id in seen:
            raise ManifestValidationError(f"Row {row_number} duplicates source_id {source_id!r}.")
        seen.add(source_id)
        for column in SOURCE_REQUIRED_COLUMNS:
            if not row.get(column, "").strip():
                raise ManifestValidationError(f"Row {row_number} is missing a value for {column}.")


def load_source_manifest(path: str | Path, *, require_audio: bool = True) -> list[dict[str, str]]:
    """Load and validate the source catalog without copying any source audio."""
    manifest_path = Path(path)
    headers, raw_rows = _read_rows(manifest_path)
    aliases = {
        "condition": "recording_condition",
        "provenance": "provenance_or_license_note",
        "license_note": "provenance_or_license_note",
    }
    _require_columns(headers, SOURCE_REQUIRED_COLUMNS, aliases)
    if not raw_rows:
        raise ManifestValidationError("The source manifest is empty.")
    _validate_source_identity(raw_rows)

    rows: list[dict[str, str]] = []
    for row_number, raw_row in enumerate(raw_rows, start=2):
        row = _canonicalize_row(raw_row)
        source_path = Path(row["source_audio_path"])
        if not source_path.is_absolute():
            source_path = manifest_path.parent / source_path
        if require_audio:
            try:
                if not source_path.is_file():
                    raise ManifestValidationError(
                        f"Row {row_number} source audio is unavailable for source_id "
                        f"{row['source_id']!r}."
                    )
            except OSError as exc:
                raise ManifestValidationError(
                    f"Row {row_number} source audio cannot be inspected for source_id "
                    f"{row['source_id']!r}."
                ) from exc
        rows.append(row)
    return rows


def load_clip_manifest(path: str | Path, *, require_audio: bool = False) -> list[dict[str, str]]:
    """Load the generated clip manifest and validate its reproducibility fields."""
    manifest_path = Path(path)
    headers, raw_rows = _read_rows(manifest_path)
    aliases = {"condition": "recording_condition"}
    _require_columns(headers, CLIP_REQUIRED_COLUMNS, aliases)
    if not raw_rows:
        raise ManifestValidationError("The clip manifest is empty.")

    seen_clip_ids: set[str] = set()
    rows: list[dict[str, str]] = []
    for row_number, raw_row in enumerate(raw_rows, start=2):
        row = _canonicalize_row(raw_row)
        source_id = row.get("source_id", "").strip()
        clip_id = row.get("clip_id", "").strip()
        if not source_id or not SOURCE_ID_PATTERN.fullmatch(source_id):
            raise ManifestValidationError(f"Row {row_number} has an invalid source_id.")
        if not clip_id or clip_id in seen_clip_ids:
            raise ManifestValidationError(f"Row {row_number} has a duplicate or empty clip_id.")
        seen_clip_ids.add(clip_id)
        for column in CLIP_REQUIRED_COLUMNS:
            if not row.get(column, "").strip():
                raise ManifestValidationError(f"Row {row_number} is missing a value for {column}.")
        try:
            length = float(row["clip_length_s"])
        except ValueError as exc:
            raise ManifestValidationError(
                f"Row {row_number} has an invalid clip_length_s."
            ) from exc
        if length <= 0:
            raise ManifestValidationError(f"Row {row_number} has a non-positive clip length.")

        clip_path = Path(row["audio_path"])
        if not clip_path.is_absolute():
            clip_path = manifest_path.parent / clip_path
        if require_audio and not clip_path.is_file():
            raise ManifestValidationError(
                f"Row {row_number} clip audio is unavailable for clip_id {clip_id!r}."
            )
        rows.append(row)
    return rows


def resolve_manifest_path(manifest_path: str | Path, value: str | Path) -> Path:
    path = Path(value)
    return path if path.is_absolute() else Path(manifest_path).parent / path


def relative_manifest_path(manifest_path: str | Path, value: str | Path) -> str:
    """Return a portable path relative to the manifest, never an absolute local path."""
    manifest_parent = Path(manifest_path).parent.resolve()
    path = Path(value).resolve()
    try:
        return path.relative_to(manifest_parent).as_posix()
    except ValueError:
        return path.name
