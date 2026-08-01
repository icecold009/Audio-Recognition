from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from io import BytesIO
from pathlib import Path
import threading
from unittest.mock import MagicMock, patch

import pytest

from web import app as web_app
from shazam_project.recorder import AudioInputError

from .test_web import _wav_bytes


MIGRATION_PATH = Path(__file__).parents[1] / "supabase" / "migrations" / "20260801145213_production_rate_limits.sql"


@pytest.fixture(autouse=True)
def reset_quota_state(monkeypatch):
    monkeypatch.setattr(web_app, "APP_ENV", "development")
    monkeypatch.setattr(web_app, "INTERNAL_API_SECRET", "")
    monkeypatch.setattr(web_app, "DAILY_LIMIT", 15)
    monkeypatch.setattr(web_app, "MONTHLY_LIMIT", 475)
    monkeypatch.setattr(web_app, "COOLDOWN_SECONDS", 30)
    web_app.memory_quota_by_client.clear()
    yield
    web_app.memory_quota_by_client.clear()


def test_migration_contains_atomic_restricted_invoker_quota_controls():
    sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    assert "alter table public.api_usage enable row level security" in sql
    assert "for update" in sql
    assert "security invoker" in sql
    assert "set search_path = pg_catalog, public" in sql
    assert "create or replace function public.check_api_quota" in sql
    assert "create or replace function public.consume_api_quota" in sql
    assert "revoke all on function public.check_api_quota" in sql
    assert "revoke all on function public.consume_api_quota" in sql
    assert "from public, anon, authenticated" in sql
    assert "to service_role" in sql
    assert "raw ip" in sql
    assert "create schema if not exists private" not in sql


def test_migration_grants_only_minimum_usage_table_privileges():
    sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    assert "grant select, insert, update on table public.api_usage to service_role" in sql
    assert "grant all on table public.api_usage" not in sql


def test_quota_functions_are_service_role_only():
    sql = MIGRATION_PATH.read_text(encoding="utf-8").lower()

    for function_name in ("check_api_quota", "consume_api_quota"):
        revoke = f"revoke all on function public.{function_name}"
        grant = f"grant execute on function public.{function_name}"
        assert revoke in sql
        assert "from public, anon, authenticated" in sql[sql.index(revoke):]
        assert grant in sql
        assert "to service_role" in sql[sql.index(grant):]


def test_development_daily_limit_is_stable(monkeypatch):
    monkeypatch.setattr(web_app, "DAILY_LIMIT", 2)
    monkeypatch.setattr(web_app, "COOLDOWN_SECONDS", 0)
    client_id = "a" * 64

    assert web_app._consume_quota(client_id)["blocked"] is False
    assert web_app._consume_quota(client_id)["blocked"] is False
    blocked = web_app._consume_quota(client_id)

    assert blocked["blocked"] is True
    assert blocked["payload"]["status"] == "rate_limited"
    assert blocked["payload"]["error_code"] == "daily_limit"


def test_development_monthly_limit_is_stable(monkeypatch):
    monkeypatch.setattr(web_app, "DAILY_LIMIT", 10)
    monkeypatch.setattr(web_app, "MONTHLY_LIMIT", 1)
    monkeypatch.setattr(web_app, "COOLDOWN_SECONDS", 0)
    client_id = "b" * 64

    assert web_app._consume_quota(client_id)["blocked"] is False
    blocked = web_app._consume_quota(client_id)

    assert blocked["payload"]["error_code"] == "monthly_limit"


def test_development_cooldown_has_retry_after(monkeypatch):
    monkeypatch.setattr(web_app, "COOLDOWN_SECONDS", 30)
    client_id = "c" * 64

    assert web_app._consume_quota(client_id)["blocked"] is False
    blocked = web_app._consume_quota(client_id)

    assert blocked["payload"]["error_code"] == "cooldown"
    assert blocked["payload"]["retry_after_seconds"] >= 1


def test_rate_limited_response_sets_retry_after_header(monkeypatch):
    cfg = MagicMock(max_upload_bytes=10 * 1024 * 1024)
    monkeypatch.setattr(web_app, "load_config", lambda: cfg)
    monkeypatch.setattr(web_app.matcher, "match_audio", lambda *_args: {"status": "matched"})
    client = web_app.app.test_client()
    upload = {"file": (BytesIO(_wav_bytes()), "sample.wav")}

    with patch.object(web_app, "_load_web_upload", return_value=object()):
        first = client.post("/api/match", data=upload, content_type="multipart/form-data")
        second = client.post(
            "/api/match",
            data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
            content_type="multipart/form-data",
        )

    assert first.status_code == 200
    assert second.status_code == 429
    assert second.get_json()["status"] == "rate_limited"
    assert second.get_json()["error_code"] == "cooldown"
    assert int(second.headers["Retry-After"]) >= 1


@pytest.mark.parametrize("error_code", ["cooldown", "daily_limit", "monthly_limit"])
def test_all_rate_limit_codes_have_retry_after_headers(monkeypatch, error_code):
    monkeypatch.setattr(web_app, "_check_rate_limits", lambda _client: web_app._rate_limited_decision(
        error_code, "Rate limit reached.", 17
    ))
    monkeypatch.setattr(web_app, "_load_web_upload", lambda *_args: object())

    response = web_app.app.test_client().post(
        "/api/match",
        data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 429
    assert response.get_json()["status"] == "rate_limited"
    assert response.get_json()["error_code"] == error_code
    assert response.headers["Retry-After"] == "17"


def test_concurrent_development_consumption_is_bounded(monkeypatch):
    monkeypatch.setattr(web_app, "DAILY_LIMIT", 3)
    monkeypatch.setattr(web_app, "COOLDOWN_SECONDS", 0)
    client_id = "d" * 64

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda _item: web_app._consume_quota(client_id), range(12)))

    assert sum(not result.get("blocked", False) for result in results) == 3
    assert sum(result.get("blocked", False) for result in results) == 9


def test_concurrent_production_consumption_delegates_bounded_atomic_decision(monkeypatch):
    state = {"count": 0}
    lock = threading.Lock()

    class FakeSupabase:
        def rpc(self, name, _params):
            assert name == "consume_api_quota"
            return self

        def execute(self):
            with lock:
                if state["count"] >= 3:
                    data = {"allowed": False, "reason": "daily_limit", "retry_after_seconds": 60}
                else:
                    state["count"] += 1
                    data = {"allowed": True}
            return type("Response", (), {"data": data})()

    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", FakeSupabase())

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(lambda _item: web_app._consume_quota("g" * 64), range(12)))

    assert sum(not result.get("blocked", False) for result in results) == 3
    assert sum(result.get("blocked", False) for result in results) == 9


def test_production_quota_uses_one_rpc_operation(monkeypatch):
    calls = []

    class FakeResponse:
        data = {"allowed": True}

    class FakeSupabase:
        def rpc(self, name, params):
            calls.append((name, params))
            return self

        def execute(self):
            return FakeResponse()

    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", FakeSupabase())

    result = web_app._consume_quota("e" * 64)

    assert result == {"blocked": False}
    assert len(calls) == 1
    assert calls[0][0] == "consume_api_quota"
    assert calls[0][1]["p_client_id_hash"] == "e" * 64


def test_production_preflight_is_read_only_and_uses_check_rpc(monkeypatch):
    calls = []

    class FakeResponse:
        data = {"allowed": True}

    class FakeSupabase:
        def rpc(self, name, params):
            calls.append((name, params))
            return self

        def execute(self):
            return FakeResponse()

    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", FakeSupabase())

    assert web_app._check_rate_limits("a" * 64) == {"blocked": False}
    assert [name for name, _params in calls] == ["check_api_quota"]


def test_blocked_production_preflight_never_loads_upload(monkeypatch):
    calls = []

    class FakeSupabase:
        def rpc(self, name, _params):
            calls.append(name)
            return self

        def execute(self):
            return type("Response", (), {"data": {
                "allowed": False,
                "reason": "daily_limit",
                "retry_after_seconds": 90,
            }})()

    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", FakeSupabase())
    with patch.object(web_app, "_load_web_upload") as loader:
        response = web_app.app.test_client().post(
            "/api/match",
            data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 429
    assert response.headers["Retry-After"] == "90"
    loader.assert_not_called()
    assert calls == ["check_api_quota"]


def test_malformed_production_audio_does_not_consume_quota(monkeypatch):
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", object())
    monkeypatch.setattr(web_app, "_check_rate_limits", lambda _client: {"blocked": False})
    monkeypatch.setattr(
        web_app,
        "_load_web_upload",
        lambda *_args: (_ for _ in ()).throw(AudioInputError("malformed_wav", "invalid")),
    )
    with patch.object(web_app, "_consume_quota") as consume:
        response = web_app.app.test_client().post(
            "/api/match",
            data={"file": (BytesIO(b"not wav"), "sample.wav")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    consume.assert_not_called()


def test_production_database_failure_is_not_fail_open(monkeypatch):
    class BrokenSupabase:
        def rpc(self, *_args, **_kwargs):
            raise RuntimeError("database unavailable")

    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", BrokenSupabase())

    result = web_app._consume_quota("f" * 64)

    assert result == {"service_error": True}


def test_missing_production_configuration_returns_503(monkeypatch):
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "")
    monkeypatch.setattr(web_app, "supabase", None)

    response = web_app.app.test_client().post("/api/match")

    assert response.status_code == 503
    assert response.get_json() == {
        "status": "error",
        "error_code": "quota_unavailable",
        "error": "Production quota service is unavailable.",
    }


def test_production_database_failure_returns_503(monkeypatch):
    monkeypatch.setattr(web_app, "APP_ENV", "production")
    monkeypatch.setattr(web_app, "SUPABASE_URL", "https://project.supabase.co")
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", "server-only")
    monkeypatch.setattr(web_app, "CLIENT_ID_HMAC_SECRET", "separate-secret")
    monkeypatch.setattr(web_app, "supabase", object())
    monkeypatch.setattr(web_app, "load_config", lambda: MagicMock())
    monkeypatch.setattr(web_app, "_load_web_upload", lambda *_args: object())
    monkeypatch.setattr(web_app, "_consume_quota", lambda _client: {"service_error": True})

    response = web_app.app.test_client().post(
        "/api/match",
        data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
        content_type="multipart/form-data",
    )

    assert response.status_code == 503
    assert response.get_json()["error_code"] == "quota_unavailable"


def test_development_fallback_is_visible_in_status():
    response = web_app.app.test_client().get("/api/status")
    body = response.get_json()

    assert response.status_code == 200
    assert body["quota_mode"] == "development-memory"
    assert body["production_grade_quotas_enabled"] is False


def test_origin_never_authenticates_without_api_secret(monkeypatch, tmp_path):
    monkeypatch.setattr(web_app, "INTERNAL_API_SECRET", "server-only-secret")
    response = web_app.app.test_client().post(
        "/api/match",
        data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
        headers={"Origin": "http://localhost"},
    )

    assert response.status_code == 401


def test_forwarded_ip_is_ignored_without_trusted_proxy_configuration(monkeypatch):
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_COUNT", 0)
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_IPS", set())
    with web_app.app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    ):
        assert web_app._get_client_ip() == "203.0.113.10"


def test_forwarded_ip_uses_only_explicit_trusted_proxy_chain(monkeypatch):
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_COUNT", 1)
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_IPS", {"203.0.113.10"})
    with web_app.app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"X-Forwarded-For": "198.51.100.20"},
    ):
        assert web_app._get_client_ip() == "198.51.100.20"


def test_multi_hop_forwarded_ip_validates_every_proxy_hop(monkeypatch):
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_COUNT", 2)
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_IPS", {"203.0.113.10", "198.51.100.30"})
    with web_app.app.test_request_context(
        "/",
        environ_base={"REMOTE_ADDR": "203.0.113.10"},
        headers={"X-Forwarded-For": "198.51.100.20, 198.51.100.30"},
    ):
        assert web_app._get_client_ip() == "198.51.100.20"


def test_multi_hop_forwarded_ip_ignores_incomplete_or_spoofed_chain(monkeypatch):
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_COUNT", 2)
    monkeypatch.setattr(web_app, "TRUSTED_PROXY_IPS", {"203.0.113.10", "198.51.100.30"})
    for chain in ("198.51.100.20", "198.51.100.20, 192.0.2.99"):
        with web_app.app.test_request_context(
            "/",
            environ_base={"REMOTE_ADDR": "203.0.113.10"},
            headers={"X-Forwarded-For": chain},
        ):
            assert web_app._get_client_ip() == "203.0.113.10"


def test_invalid_audio_does_not_consume_quota(monkeypatch):
    monkeypatch.setattr(web_app, "load_config", lambda: MagicMock())
    monkeypatch.setattr(
        web_app,
        "_load_web_upload",
        lambda *_args: (_ for _ in ()).throw(AudioInputError("malformed_wav", "invalid")),
    )
    with patch.object(web_app, "_consume_quota") as consume:
        response = web_app.app.test_client().post(
            "/api/match",
            data={"file": (BytesIO(b"not wav"), "sample.wav")},
            content_type="multipart/form-data",
        )

    assert response.status_code == 400
    consume.assert_not_called()


def test_service_role_key_is_not_returned_by_status(monkeypatch):
    secret = "do-not-return-this"
    monkeypatch.setattr(web_app, "SUPABASE_SERVICE_ROLE_KEY", secret)
    response = web_app.app.test_client().get("/api/status")

    assert secret not in response.get_data(as_text=True)


def test_client_identifier_is_hmac_derived_and_not_an_ip():
    client_ip = "198.51.100.20"
    with web_app.app.test_request_context("/", environ_base={"REMOTE_ADDR": client_ip}):
        client_id = web_app._client_id_hash()

    assert client_id != client_ip
    assert len(client_id) == 64
    assert all(character in "0123456789abcdef" for character in client_id)
