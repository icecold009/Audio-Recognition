from __future__ import annotations

from io import BytesIO
from pathlib import Path
from types import SimpleNamespace

from shazam_project.config import AppConfig
from web import app as web_app


def _always_available(tool: str) -> str:
    return f"/usr/bin/{tool}"


def _reset_runtime(monkeypatch):
    monkeypatch.setattr(web_app, "APP_ENV", "development")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "")
    monkeypatch.setattr(web_app, "INTERNAL_API_SECRET", "")
    monkeypatch.setattr(web_app, "supabase", None)
    web_app.app.config["MAX_CONTENT_LENGTH"] = 25 * 1024 * 1024
    monkeypatch.setattr(web_app, "load_config", lambda: AppConfig(audd_api_token="TOKEN"))


def test_healthz_is_dependency_free(monkeypatch):
    _reset_runtime(monkeypatch)

    response = web_app.app.test_client().get("/healthz")

    assert response.status_code == 200
    assert response.get_json() == {"status": "ok"}


def test_development_readyz_reports_backend_and_does_not_require_supabase(monkeypatch):
    _reset_runtime(monkeypatch)
    monkeypatch.setattr(web_app.shutil, "which", _always_available)

    response = web_app.app.test_client().get("/readyz")

    assert response.status_code == 200
    body = response.get_json()
    assert body["status"] == "ready"
    assert body["quota_mode"] == "development-memory"
    assert body["checks"]["production_configuration"] == {"ok": True, "required": False}
    assert body["checks"]["supabase_quota"] == {"ok": True, "required": False}
    assert body["checks"]["recognition_backend"]["backends"]["audd"] is True


def test_production_readyz_fails_closed_without_quota_configuration(monkeypatch):
    _reset_runtime(monkeypatch)
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app.shutil, "which", _always_available)

    response = web_app.app.test_client().get("/readyz")

    assert response.status_code == 503
    body = response.get_json()
    assert body["status"] == "not_ready"
    assert body["error_code"] == "not_ready"
    assert body["checks"]["production_configuration"]["ok"] is False
    assert body["checks"]["supabase_quota"]["ok"] is False
    assert "SUPABASE" not in response.get_data(as_text=True)


def test_production_readyz_probes_supabase_quota_without_consuming_or_exposing_hash(monkeypatch):
    _reset_runtime(monkeypatch)
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://supabase.example")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "service-role-secret")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "hmac-secret")
    monkeypatch.setattr(web_app.shutil, "which", _always_available)
    monkeypatch.setattr(
        web_app,
        "load_config",
        lambda: AppConfig(audd_api_token="TOKEN"),
    )

    class FakeSupabase:
        def __init__(self):
            self.calls = []

        def rpc(self, name, params):
            self.calls.append((name, params))
            return self

        def execute(self):
            return SimpleNamespace(data={"allowed": True})

    fake = FakeSupabase()
    monkeypatch.setattr(web_app, "supabase", fake)

    response = web_app.app.test_client().get("/readyz")

    assert response.status_code == 200
    assert response.get_json()["checks"]["supabase_quota"]["ok"] is True
    assert len(fake.calls) == 1
    assert fake.calls[0][0] == "check_api_quota"
    assert fake.calls[0][1]["p_client_id_hash"] not in response.get_data(as_text=True)


def test_production_readyz_sanitizes_quota_probe_failure(monkeypatch, caplog):
    _reset_runtime(monkeypatch)
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://supabase.example")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "service-role-secret")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "hmac-secret")
    monkeypatch.setattr(web_app.shutil, "which", _always_available)
    private_text = "https://private.example/db?password=secret C:\\private\\trace"

    class BrokenSupabase:
        def rpc(self, _name, _params):
            raise RuntimeError(private_text)

    monkeypatch.setattr(web_app, "supabase", BrokenSupabase())

    response = web_app.app.test_client().get("/readyz")

    assert response.status_code == 503
    assert private_text not in response.get_data(as_text=True)
    assert private_text not in caplog.text
    assert "readiness_quota" in caplog.text
    assert "quota_readiness_failed" in caplog.text


def test_status_is_non_secret_and_reports_runtime_contract(monkeypatch):
    _reset_runtime(monkeypatch)
    monkeypatch.setattr(web_app, "APP_ENV", "development")
    monkeypatch.setattr(
        web_app,
        "load_config",
        lambda: AppConfig(audd_api_token="TOKEN", rapidapi_key="private-rapid-key"),
    )
    monkeypatch.setattr(web_app.shutil, "which", _always_available)

    response = web_app.app.test_client().get("/api/status")

    assert response.status_code == 200
    body = response.get_json()
    assert body["quota_mode"] == "development-memory"
    assert body["production_grade_quotas_enabled"] is False
    assert body["rapidapi_configured"] is True
    assert "private-rapid-key" not in response.get_data(as_text=True)
    assert "SUPABASE_SERVICE_ROLE_KEY" not in response.get_data(as_text=True)


def test_external_flask_smoke_covers_invalid_upload_and_mocked_match(monkeypatch):
    _reset_runtime(monkeypatch)
    client = web_app.app.test_client()
    monkeypatch.setattr(
        web_app.matcher,
        "match_audio",
        lambda _clip, _config: {"status": "matched", "title": "Smoke", "artist": "Test"},
    )

    invalid = client.post(
        "/api/match",
        data={"file": (BytesIO(b"not a wav"), "invalid.wav")},
        content_type="multipart/form-data",
    )
    matched = client.post(
        "/api/match",
        data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
        content_type="multipart/form-data",
    )

    assert invalid.status_code == 400
    assert invalid.get_json()["status"] == "invalid_audio"
    assert matched.status_code == 200
    assert matched.get_json()["status"] == "matched"


def test_deployment_manifests_define_non_root_runtime_and_smoke_contract():
    root = Path(__file__).parents[1]
    dockerfile = (root / "Dockerfile").read_text(encoding="utf-8")
    compose = (root / "compose.yaml").read_text(encoding="utf-8")
    render = (root / "render.yaml").read_text(encoding="utf-8")
    ignore = (root / ".dockerignore").read_text(encoding="utf-8")
    gunicorn = (root / "gunicorn.conf.py").read_text(encoding="utf-8")

    assert "python:3.12-slim-bookworm" in dockerfile
    assert "ffmpeg" in dockerfile
    assert "libchromaprint-tools" in dockerfile
    assert "USER 10001:10001" in dockerfile
    assert "gunicorn" in dockerfile
    assert "healthz" in dockerfile
    assert "--read-only" not in dockerfile
    assert "read_only: true" in compose
    assert "/tmp:size=64m" in compose
    assert "healthCheckPath: /healthz" in render
    assert "sync: false" in render
    assert ".env" in ignore
    assert "coverage.xml" in ignore
    assert "PORT" in gunicorn
    assert "timeout" in gunicorn


def _wav_bytes(duration_seconds: float = 1.5, sample_rate: int = 8000) -> bytes:
    import wave

    frame_count = int(duration_seconds * sample_rate)
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(b"\x00\x00" * frame_count)
    return output.getvalue()
