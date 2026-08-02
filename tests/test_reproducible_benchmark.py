from __future__ import annotations

import csv
from pathlib import Path
from types import SimpleNamespace

import numpy as np
import pytest
import soundfile as sf

from scripts import benchmark, record_benchmark
from scripts.evaluation import ManifestValidationError, load_source_manifest
from scripts.update_readme import update_readme, validate_complete_results
from shazam_project.config import AppConfig


def _wav(path: Path, seconds: float = 1.5, sample_rate: int = 8000) -> Path:
    samples = np.zeros(int(seconds * sample_rate), dtype=np.float32)
    sf.write(path, samples, sample_rate, subtype="PCM_16")
    return path


def _sources_csv(path: Path, *, complete: bool = True, duplicate: bool = False) -> Path:
    path.mkdir(parents=True, exist_ok=True)
    source = path / "source.wav"
    source.write_bytes(b"source")
    rows = [
        {
            "source_id": "track-001",
            "source_audio_path": "source.wav",
            "title": "Example Song",
            "artist": "Example Artist",
            "genre": "pop",
            "era": "2010s",
            "recording_condition": "speaker_mic_room",
            "provenance_or_license_note": "Operator-owned source",
        }
    ]
    if duplicate:
        rows.append(dict(rows[0]))
    csv_path = path / "sources.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    if not complete:
        text = csv_path.read_text(encoding="utf-8").replace(",Operator-owned source", ",")
        csv_path.write_text(text, encoding="utf-8")
    return csv_path


def _write_clip_manifest(path: Path, rows: list[dict[str, str]]) -> Path:
    manifest = path / "manifest.csv"
    with manifest.open("w", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(handle, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)
    return manifest


def _clip_manifest(path: Path, clip: Path, *, provider_id: str = "") -> Path:
    row = {
        "source_id": "track-001",
        "clip_id": "track-001_4s",
        "audio_path": clip.name,
        "expected_title": "Example Song",
        "expected_artist": "Example Artist",
        "genre": "pop",
        "era": "2010s",
        "recording_condition": "speaker_mic_room",
        "clip_length_s": "4",
    }
    if provider_id:
        row["rapidapi_id"] = provider_id
    return _write_clip_manifest(path, [row])


def test_source_manifest_requires_all_provenance_fields_and_existing_audio(tmp_path):
    valid = _sources_csv(tmp_path)
    assert load_source_manifest(valid)[0]["recording_condition"] == "speaker_mic_room"

    incomplete = _sources_csv(tmp_path / "incomplete", complete=False)
    with pytest.raises(ManifestValidationError, match="provenance_or_license_note"):
        load_source_manifest(incomplete)


def test_source_manifest_rejects_duplicate_unstable_ids(tmp_path):
    path = tmp_path / "duplicate"
    path.mkdir()
    manifest = _sources_csv(path, duplicate=True)
    with pytest.raises(ManifestValidationError, match="duplicates source_id"):
        load_source_manifest(manifest)


def test_recording_resume_preserves_verified_clip(monkeypatch, tmp_path):
    output_dir = tmp_path / "clips"
    output_dir.mkdir()
    existing = _wav(output_dir / "track-001_4s.wav", seconds=4)
    before = existing.read_bytes()
    source = {
        "source_id": "track-001",
        "source_audio_path": str(tmp_path / "source.wav"),
        "_resolved_source_path": str(tmp_path / "source.wav"),
        "title": "Song",
        "artist": "Artist",
        "genre": "pop",
        "era": "2010s",
        "recording_condition": "room",
        "provenance_or_license_note": "owned",
    }
    _wav(tmp_path / "source.wav", seconds=15)
    monkeypatch.setattr(
        record_benchmark,
        "_decode_source",
        lambda _path: (np.zeros(15 * 8000, dtype=np.float32), 8000),
    )
    monkeypatch.setattr(
        record_benchmark,
        "sd",
        SimpleNamespace(
            playrec=lambda *args, **kwargs: np.zeros(15 * 8000, dtype=np.float32),
            stop=lambda: None,
        ),
    )

    record_benchmark._record_source(
        source,
        output_dir,
        1,
        2,
        pending_lengths=[8],
        manifest_path=tmp_path / "manifest.csv",
    )

    assert existing.read_bytes() == before
    assert (output_dir / "track-001_8s.wav").is_file()


def test_benchmark_cache_is_deterministic_and_does_not_store_credentials(monkeypatch, tmp_path):
    clip = _wav(tmp_path / "clip.wav")
    manifest = _clip_manifest(tmp_path, clip)
    output = tmp_path / "result.json"
    cache_dir = tmp_path / "cache"
    calls = 0

    def fake_provider(_clip, _config, timeout):
        nonlocal calls
        calls += 1
        assert timeout == 11
        return {
            "status": "matched",
            "title": "Example Song",
            "artist": "Example Artist",
            "result": {"key": "stable-provider-id"},
        }

    monkeypatch.setattr(
        benchmark,
        "load_config",
        lambda _path: AppConfig(audd_api_token="", rapidapi_key="private-key"),
    )
    monkeypatch.setitem(
        benchmark.BACKENDS,
        "rapidapi",
        ("RapidAPI/Shazam", fake_provider, "rapidapi_key"),
    )
    first = benchmark.run(
        manifest,
        output,
        11,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=cache_dir,
    )
    second = benchmark.run(
        manifest,
        output,
        11,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=cache_dir,
    )

    assert calls == 1
    assert first["metadata"]["cache_state"] == "cold"
    assert second["metadata"]["cache_state"] == "warm"
    assert second["records"][0]["cache_hit"] is True
    cache_text = next(cache_dir.glob("*.json")).read_text(encoding="utf-8")
    assert "private-key" not in cache_text
    assert "Authorization" not in cache_text


@pytest.mark.parametrize(
    ("hits", "misses", "expected"),
    [(0, 0, "empty"), (0, 2, "cold"), (2, 0, "warm"), (2, 1, "mixed")],
)
def test_cache_state_distinguishes_empty_cold_warm_and_mixed(hits, misses, expected):
    assert benchmark._cache_state(hits, misses) == expected


def test_refresh_cache_calls_backend_again(monkeypatch, tmp_path):
    clip = _wav(tmp_path / "clip.wav")
    manifest = _clip_manifest(tmp_path, clip)
    calls = 0

    def fake_provider(_clip, _config, timeout):
        nonlocal calls
        calls += 1
        return {"status": "no_match", "result": None}

    monkeypatch.setattr(
        benchmark,
        "load_config",
        lambda _path: AppConfig(audd_api_token="", rapidapi_key="key"),
    )
    monkeypatch.setitem(
        benchmark.BACKENDS,
        "rapidapi",
        ("RapidAPI/Shazam", fake_provider, "rapidapi_key"),
    )
    kwargs = {
        "backends": ["rapidapi"],
        "cache_dir": tmp_path / "cache",
        "refresh_cache": True,
    }
    benchmark.run(manifest, tmp_path / "one.json", 15, tmp_path / ".env", **kwargs)
    benchmark.run(manifest, tmp_path / "two.json", 15, tmp_path / ".env", **kwargs)
    assert calls == 2


def test_incomplete_credentials_never_call_backend_or_claim_complete(monkeypatch, tmp_path):
    clip = _wav(tmp_path / "clip.wav")
    manifest = _clip_manifest(tmp_path, clip)
    called = False

    def forbidden_provider(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("provider call should not occur")

    monkeypatch.setattr(benchmark, "load_config", lambda _path: AppConfig(audd_api_token=""))
    monkeypatch.setitem(
        benchmark.BACKENDS,
        "rapidapi",
        ("RapidAPI/Shazam", forbidden_provider, "rapidapi_key"),
    )
    results = benchmark.run(
        manifest,
        tmp_path / "result.json",
        15,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=tmp_path / "cache",
    )
    assert called is False
    assert results["metadata"]["complete"] is False
    assert results["records"][0]["status"] == "not_configured"
    assert not (tmp_path / "cache").exists()


def _configured_rapidapi(monkeypatch, provider):
    monkeypatch.setattr(
        benchmark,
        "load_config",
        lambda _path: AppConfig(audd_api_token="", rapidapi_key="key"),
    )
    monkeypatch.setitem(
        benchmark.BACKENDS,
        "rapidapi",
        ("RapidAPI/Shazam", provider, "rapidapi_key"),
    )


def test_one_missing_clip_is_visible_and_excluded_from_accuracy(monkeypatch, tmp_path):
    manifest = _write_clip_manifest(
        tmp_path,
        [
            {
                "source_id": "track-001",
                "clip_id": "track-001_4s",
                "audio_path": "missing.wav",
                "expected_title": "Example Song",
                "expected_artist": "Example Artist",
                "genre": "pop",
                "era": "2010s",
                "recording_condition": "room",
                "clip_length_s": "4",
            }
        ],
    )
    called = False

    def forbidden_provider(*_args, **_kwargs):
        nonlocal called
        called = True
        raise AssertionError("missing clips must not call providers")

    _configured_rapidapi(monkeypatch, forbidden_provider)
    results = benchmark.run(
        manifest,
        tmp_path / "result.json",
        15,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=tmp_path / "cache",
    )

    summary = results["backend_summary"]["rapidapi"]
    assert called is False
    assert results["metadata"]["complete"] is False
    assert results["metadata"]["missing_clip_count"] == 1
    assert results["metadata"]["cache_state"] == "empty"
    assert summary["total_clips"] == 1
    assert summary["attempted"] == 0
    assert summary["accuracy_denominator"] == 0
    assert summary["missing_inputs"] == 1
    assert results["records"][0]["error_code"] == "missing_clip"
    assert results["records"][0]["status"] == "invalid_audio"
    readme = tmp_path / "readme.md"
    readme.write_text(
        "before\n<!-- BENCHMARK_RESULTS:START -->\nold\n<!-- BENCHMARK_RESULTS:END -->\n",
        encoding="utf-8",
    )
    with pytest.raises(ValueError, match="incomplete"):
        update_readme(readme, results)
    assert "old" in readme.read_text(encoding="utf-8")


def test_all_missing_clips_mark_benchmark_incomplete_without_cache_operations(
    monkeypatch, tmp_path
):
    rows = []
    for length in ("4", "8"):
        rows.append(
            {
                "source_id": "track-001",
                "clip_id": f"track-001_{length}s",
                "audio_path": f"missing-{length}.wav",
                "expected_title": "Example Song",
                "expected_artist": "Example Artist",
                "genre": "pop",
                "era": "2010s",
                "recording_condition": "room",
                "clip_length_s": length,
            }
        )
    manifest = _write_clip_manifest(tmp_path, rows)
    _configured_rapidapi(monkeypatch, lambda *_args, **_kwargs: {"status": "matched"})

    results = benchmark.run(
        manifest,
        tmp_path / "result.json",
        15,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=tmp_path / "cache",
    )

    summary = results["backend_summary"]["rapidapi"]
    assert results["metadata"]["complete"] is False
    assert results["metadata"]["missing_clip_count"] == 2
    assert results["metadata"]["cache_state"] == "empty"
    assert summary["attempted"] == 0
    assert summary["accuracy_denominator"] == 0
    assert summary["missing_inputs"] == 2
    assert not (tmp_path / "cache").exists()


def test_mixed_present_and_missing_clips_excludes_only_missing_clip_from_denominator(
    monkeypatch, tmp_path
):
    present = _wav(tmp_path / "present.wav")
    manifest = _write_clip_manifest(
        tmp_path,
        [
            {
                "source_id": "track-001",
                "clip_id": "track-001_4s",
                "audio_path": present.name,
                "expected_title": "Example Song",
                "expected_artist": "Example Artist",
                "genre": "pop",
                "era": "2010s",
                "recording_condition": "room",
                "clip_length_s": "4",
            },
            {
                "source_id": "track-001",
                "clip_id": "track-001_8s",
                "audio_path": "missing.wav",
                "expected_title": "Example Song",
                "expected_artist": "Example Artist",
                "genre": "pop",
                "era": "2010s",
                "recording_condition": "room",
                "clip_length_s": "8",
            },
        ],
    )
    _configured_rapidapi(
        monkeypatch,
        lambda *_args, **_kwargs: {
            "status": "matched",
            "title": "Example Song",
            "artist": "Example Artist",
        },
    )

    results = benchmark.run(
        manifest,
        tmp_path / "result.json",
        15,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=tmp_path / "cache",
    )

    summary = results["backend_summary"]["rapidapi"]
    assert results["metadata"]["complete"] is False
    assert summary["total_clips"] == 2
    assert summary["attempted"] == 1
    assert summary["correct"] == 1
    assert summary["accuracy_denominator"] == 1
    assert summary["missing_inputs"] == 1
    assert results["metadata"]["cache_state"] == "cold"


def test_stable_identifier_wins_and_title_artist_is_explicit_fallback(monkeypatch, tmp_path):
    clip = _wav(tmp_path / "clip.wav")
    manifest = _clip_manifest(tmp_path, clip, provider_id="stable-id")
    config = AppConfig(audd_api_token="", rapidapi_key="key")
    monkeypatch.setitem(
        benchmark.BACKENDS,
        "rapidapi",
        (
            "RapidAPI/Shazam",
            lambda *_args, **_kwargs: {
                "status": "matched",
                "title": "Wrong title",
                "artist": "Wrong artist",
                "result": {"key": "stable-id"},
            },
            "rapidapi_key",
        ),
    )
    row = benchmark.load_clip_manifest(manifest, require_audio=False)[0]
    result = benchmark._run_backend("rapidapi", clip, row, config, 15)
    assert result["correct"] is True
    assert result["identity_method"] == "provider_identifier"


def test_aggregate_reports_rates_conditions_and_percentiles():
    records = [
        {
            "backend": "rapidapi",
            "source_id": "one",
            "clip_id": "one_4s",
            "clip_length_s": 4.0,
            "recording_condition": "near",
            "status": "matched",
            "correct": True,
            "latency_ms": 100.0,
        },
        {
            "backend": "rapidapi",
            "source_id": "one",
            "clip_id": "one_8s",
            "clip_length_s": 8.0,
            "recording_condition": "room",
            "status": "matched",
            "correct": False,
            "latency_ms": 200.0,
        },
        {
            "backend": "rapidapi",
            "source_id": "one",
            "clip_id": "one_15s",
            "clip_length_s": 15.0,
            "recording_condition": "noise",
            "status": "error",
            "error_code": "timeout",
            "correct": False,
            "latency_ms": 300.0,
        },
        {
            "backend": "rapidapi",
            "source_id": "one",
            "clip_id": "one_bad",
            "clip_length_s": 4.0,
            "recording_condition": "near",
            "status": "invalid_audio",
            "correct": False,
            "error_code": "malformed_wav",
            "latency_ms": 50.0,
        },
    ]
    summary = benchmark._aggregate(records, "rapidapi")
    assert summary["accuracy_numerator"] == 1
    assert summary["accuracy_denominator"] == 4
    assert summary["false_positives"] == 1
    assert summary["timeouts"] == 1
    assert summary["unusable_inputs"] == 1
    assert summary["latency_ms"]["p95"] == 300.0
    assert summary["by_recording_condition"]["near"]["accuracy_numerator"] == 1


def test_readme_update_refuses_incomplete_results_without_writing(tmp_path):
    readme = tmp_path / "readme.md"
    original = "before\n<!-- BENCHMARK_RESULTS:START -->\nold\n<!-- BENCHMARK_RESULTS:END -->\n"
    readme.write_text(original, encoding="utf-8")
    incomplete = {"metadata": {"complete": False}, "backend_summary": {}, "clip_count": 1}
    with pytest.raises(ValueError, match="incomplete"):
        validate_complete_results(incomplete)
    with pytest.raises(ValueError, match="incomplete"):
        update_readme(readme, incomplete)
    assert readme.read_text(encoding="utf-8") == original


def test_validator_checks_counts_even_when_metadata_claims_complete():
    results = {
        "metadata": {"complete": True, "incomplete_reasons": []},
        "clip_count": 0,
        "backend_summary": {backend: {} for backend in benchmark.BACKENDS},
        "records": [],
    }

    with pytest.raises(ValueError, match="clip_count must be greater than zero"):
        validate_complete_results(results)


def test_validator_rejects_inconsistent_denominator_even_when_metadata_claims_complete():
    records = [
        {
            "backend": backend,
            "clip_id": "track-001_4s",
            "clip_length_s": 4.0,
            "recording_condition": "room",
            "status": "matched",
            "correct": True,
        }
        for backend in benchmark.BACKENDS
    ]
    summaries = {
        backend: {
            **benchmark._aggregate(records, backend),
            "accuracy_denominator": 0,
        }
        for backend in benchmark.BACKENDS
    }
    results = {
        "metadata": {
            "complete": True,
            "incomplete_reasons": [],
            "network_region": "EU",
            "provider_plan": "reviewed-plan",
            "selected_backends": list(benchmark.BACKENDS),
        },
        "clip_count": 1,
        "backend_summary": summaries,
        "records": records,
    }

    with pytest.raises(ValueError, match="accuracy denominator is inconsistent"):
        validate_complete_results(results)


def test_readme_update_imports_only_generated_complete_metrics(tmp_path):
    readme = tmp_path / "readme.md"
    readme.write_text(
        "before\n<!-- BENCHMARK_RESULTS:START -->\nold\n<!-- BENCHMARK_RESULTS:END -->\n",
        encoding="utf-8",
    )
    records = [
        {
            "backend": backend,
            "source_id": "track-001",
            "clip_id": "track-001_4s",
            "clip_length_s": 4.0,
            "recording_condition": "room",
            "status": "matched",
            "correct": True,
            "latency_ms": 10.0,
        }
        for backend in benchmark.BACKENDS
    ]
    results = {
        "metadata": {
            "complete": True,
            "generated_at_utc": "2026-01-01T00:00:00+00:00",
            "python_version": "3.12",
            "os": "test",
            "network_region": "EU",
            "provider_plan": "reviewed-plan",
            "timeout_seconds": 15,
            "cache_state": "cold",
            "selected_backends": list(benchmark.BACKENDS),
            "incomplete_reasons": [],
        },
        "clip_count": 1,
        "backend_summary": {
            backend: benchmark._aggregate(records, backend) for backend in benchmark.BACKENDS
        },
        "records": records,
    }

    update_readme(readme, results)

    updated = readme.read_text(encoding="utf-8")
    assert "Benchmark results" in updated
    assert "reviewed-plan" in updated
    assert "\nold\n" not in updated


def test_report_generation_contains_metadata_and_metrics(tmp_path):
    clip = _wav(tmp_path / "clip.wav")
    manifest = _clip_manifest(tmp_path, clip)
    results = benchmark.run(
        manifest,
        tmp_path / "result.json",
        15,
        tmp_path / ".env",
        backends=["rapidapi"],
        cache_dir=tmp_path / "cache",
        network_region="EU",
        provider_plan="test-plan",
    )
    report = (tmp_path / "result.md").read_text(encoding="utf-8")
    assert "Generated UTC" in report
    assert "P95 ms" in report
    assert "speaker_mic_room" in report
    assert results["metadata"]["network_region"] == "EU"


def test_render_markdown_has_one_section_per_backend_and_breakdown(tmp_path):
    records = []
    for backend in benchmark.BACKENDS:
        for clip_length, condition in ((4.0, "near"), (8.0, "room")):
            records.append(
                {
                    "backend": backend,
                    "source_id": "track-001",
                    "clip_id": f"track-001_{backend}_{clip_length:g}s",
                    "clip_length_s": clip_length,
                    "recording_condition": condition,
                    "status": "matched",
                    "correct": True,
                    "latency_ms": 10.0,
                }
            )
    results = {
        "metadata": {
            "generated_at_utc": "2026-01-01T00:00:00+00:00",
            "python_version": "3.12",
            "os": "test",
            "network_region": "EU",
            "provider_plan": "test-plan",
            "timeout_seconds": 15,
            "cache_state": "cold",
        },
        "backend_summary": {
            backend: benchmark._aggregate(records, backend) for backend in benchmark.BACKENDS
        },
    }

    report = benchmark.render_markdown(results)

    for backend in benchmark.BACKENDS:
        assert report.count(f"## {backend} by clip length") == 1
        assert report.count(f"## {backend} by recording condition") == 1
