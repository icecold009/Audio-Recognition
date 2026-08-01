from __future__ import annotations

import json
import wave
from io import BytesIO
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from shazam_project import matcher
from shazam_project.config import AppConfig
from web import app as web_app

from .test_audio_pipeline import config, valid_samples


@pytest.fixture(autouse=True)
def clear_web_rate_state():
    web_app.last_request_by_ip.clear()
    yield
    web_app.last_request_by_ip.clear()


def _generated_wav(seconds: float = 1.25, sample_rate: int = 8000) -> bytes:
    samples = (
        0.25 * np.sin(2 * np.pi * 440 * np.arange(int(seconds * sample_rate)) / sample_rate)
    ).astype(np.float32)
    pcm = np.round(samples * 32767).astype("<i2")
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(pcm.tobytes())
    return output.getvalue()


def _upload(filename: str = "generated.wav"):
    return {"file": (BytesIO(_generated_wav()), filename)}


def test_status_reports_runtime_capabilities_without_secrets(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())
    monkeypatch.setattr(web_app, "supabase", None)
    monkeypatch.setattr(web_app.shutil, "which", lambda _name: None)

    response = web_app.app.test_client().get("/api/status")
    body = response.get_json()

    assert response.status_code == 200
    assert body["supported_formats"] == ["wav", "mp3", "m4a", "aac", "ogg", "flac", "webm"]
    assert body["ffmpeg_on_path"] is False
    assert body["fpcalc_on_path"] is False
    assert "SUPABASE_KEY" not in json.dumps(body)


def test_match_returns_safe_result_for_incomplete_provider_metadata(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())
    monkeypatch.setattr(
        web_app.matcher,
        "match_audio",
        lambda clip, app_config: {"status": "matched", "backend": "mock"},
    )

    response = web_app.app.test_client().post(
        "/api/match", data=_upload(), content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert response.get_json() == {"status": "matched", "backend": "mock"}


def test_invalid_audio_is_reported_without_provider_calls(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())
    matcher_call = MagicMock()
    monkeypatch.setattr(web_app.matcher, "match_audio", matcher_call)

    response = web_app.app.test_client().post(
        "/api/match",
        data={"file": (BytesIO(b"not-a-wav"), "broken.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 400
    assert response.get_json()["error_code"] == "malformed_wav"
    matcher_call.assert_not_called()


def test_missing_ffmpeg_is_reported_for_non_wav_upload(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())
    monkeypatch.setattr("shazam_project.recorder.shutil.which", lambda name: None)

    response = web_app.app.test_client().post(
        "/api/match", data=_upload("generated.mp3"), content_type="multipart/form-data"
    )

    assert response.status_code == 400
    assert response.get_json() == {
        "status": "invalid_audio",
        "error_code": "ffmpeg_unavailable",
        "error": "FFmpeg is required for this audio format.",
    }


def test_rate_limit_response_stops_processing(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())
    monkeypatch.setattr(
        web_app,
        "_check_rate_limits",
        lambda _client: {
            "blocked": True,
            "status_code": 429,
            "payload": {
                "status": "rate_limited",
                "error_code": "daily_limit",
                "error": "Daily recognition limit reached.",
            },
        },
    )
    loader = MagicMock()
    monkeypatch.setattr(web_app, "_load_web_upload", loader)

    response = web_app.app.test_client().post(
        "/api/match", data=_upload(), content_type="multipart/form-data"
    )

    assert response.status_code == 429
    assert response.get_json()["status"] == "rate_limited"
    loader.assert_not_called()


def test_supabase_failure_does_not_leak_details_in_status(monkeypatch, caplog):
    class BrokenSupabase:
        def table(self, *_args, **_kwargs):
            raise RuntimeError("supabase private endpoint")

    monkeypatch.setattr(web_app, "load_config", lambda: config())
    monkeypatch.setattr(web_app, "supabase", BrokenSupabase())

    with caplog.at_level("ERROR"):
        response = web_app.app.test_client().get("/api/status")

    assert response.status_code == 200
    assert "supabase private endpoint" not in response.get_data(as_text=True)
    assert "supabase private endpoint" not in caplog.text


def test_missing_backend_configuration_is_visible_without_credentials(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: AppConfig(audd_api_token=""))

    response = web_app.app.test_client().post(
        "/api/match", data=_upload(), content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "not_configured"


def test_generated_wav_exercises_flask_client_end_to_end(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: config())

    response = web_app.app.test_client().post(
        "/api/match", data=_upload(), content_type="multipart/form-data"
    )

    assert response.status_code == 200
    assert response.get_json()["status"] == "not_configured"
    assert response.get_json()["attempts"]


def test_frontend_uses_text_nodes_and_unknown_metadata_fallbacks():
    source = Path("web/static/app.js").read_text(encoding="utf-8")

    assert "data.title || '(unknown)'" in source
    assert "data.artist || '(unknown)'" in source
    assert "data.album || '(unknown)'" in source
    assert "title.textContent" in source
    assert "artist.textContent" in source
    assert "album.textContent" in source
    assert "resultDiv.innerHTML = `" not in source


def test_provider_fallback_reaches_local_backend_after_external_failures():
    clip = matcher.AudioClip(valid_samples(16000), 16000, "fallback")
    app_config = config(
        rapidapi_key="rapid",
        acoustid_api_key="acoustid",
        audd_api_token="audd",
        fingerprint_index_path="index.json",
    )
    with (
        patch.object(matcher, "match_audio_shazam", return_value={"status": "no_match"}),
        patch.object(
            matcher,
            "match_audio_acoustid",
            return_value={"status": "error", "error_code": "timeout"},
        ),
        patch.object(matcher, "_match_audio_audd", return_value={"status": "no_match"}),
        patch.object(
            matcher,
            "match_audio_local",
            return_value={"status": "matched", "title": "Local Song"},
        ),
    ):
        result = matcher.match_audio(clip, app_config)

    assert result["status"] == "matched"
    assert result["backend"] == "local"
    assert [attempt["status"] for attempt in result["attempts"]] == [
        "no_match",
        "error",
        "no_match",
        "matched",
    ]


def test_provider_secret_is_absent_from_response_and_logs(caplog):
    secret = r"C:\private\provider-secret"
    clip = matcher.AudioClip(valid_samples(44100), 44100, "provider", path=Path(secret))

    with (
        patch.object(matcher, "match_audio_shazam", side_effect=RuntimeError(secret)),
        caplog.at_level("ERROR"),
    ):
        result = matcher.match_audio(clip, config(rapidapi_key="rapid-secret"))

    serialized = json.dumps(result)
    assert result["attempts"][0]["error_code"] == "provider_error"
    assert secret not in serialized
    assert secret not in caplog.text


def test_fpcalc_stderr_is_absent_from_response_and_logs(caplog):
    stderr = "private fpcalc stderr with provider-secret"
    process = MagicMock(returncode=1, stdout="", stderr=stderr)
    clip = matcher.AudioClip(valid_samples(44100), 44100, "provider")

    with (
        patch.object(matcher.shutil, "which", return_value="fpcalc"),
        patch.object(matcher.subprocess, "run", return_value=process),
        caplog.at_level("ERROR"),
    ):
        result = matcher.match_audio_acoustid(clip, AppConfig("", acoustid_api_key="acoustid"))

    assert result["error_code"] == "fpcalc_error"
    assert stderr not in json.dumps(result)
    assert stderr not in caplog.text
