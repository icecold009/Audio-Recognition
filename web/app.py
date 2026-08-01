from __future__ import annotations

import hashlib
import hmac
import ipaddress
import logging
import os
import secrets
import shutil
import sys
import tempfile
import threading
import time
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

from dotenv import load_dotenv
from flask_cors import CORS

if __package__ in {None, ""}:
    sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from flask import Flask, jsonify, render_template, request

from shazam_project import matcher
from shazam_project.config import AppConfig, load_config
from shazam_project.recorder import AudioInputError, convert_with_ffmpeg, load_audio_file
from supabase import Client, create_client

load_dotenv()
app = Flask(__name__, template_folder="templates", static_folder="static")

CORS_ORIGINS = [
    origin.strip() for origin in os.getenv("CORS_ORIGINS", "").split(",") if origin.strip()
]
CORS(app, origins=CORS_ORIGINS)
app.config["MAX_CONTENT_LENGTH"] = int(os.getenv("MAX_UPLOAD_BYTES", str(25 * 1024 * 1024)))

SUPPORTED_WEB_FORMATS = ("wav", "mp3", "m4a", "aac", "ogg", "flac", "webm")
SUPPORTED_WEB_SUFFIXES = {f".{extension}" for extension in SUPPORTED_WEB_FORMATS}

SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_SERVICE_ROLE_KEY = os.getenv("SUPABASE_SERVICE_ROLE_KEY", "")
CLIENT_ID_HMAC_SECRET = os.getenv("CLIENT_ID_HMAC_SECRET", "")
APP_ENV = os.getenv("APP_ENV", "production").strip().lower()


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, str(default)))
    except (TypeError, ValueError):
        return default


TRUSTED_PROXY_COUNT = max(0, _int_env("TRUSTED_PROXY_COUNT", 0))
TRUSTED_PROXY_IPS = {
    item.strip() for item in os.getenv("TRUSTED_PROXY_IPS", "").split(",") if item.strip()
}
MEMORY_LIMITER_MAX_ENTRIES = max(1, _int_env("MEMORY_LIMITER_MAX_ENTRIES", 10000))
MEMORY_LIMITER_TTL_SECONDS = max(60, _int_env("MEMORY_LIMITER_TTL_SECONDS", 86400))
_DEVELOPMENT_HMAC_SECRET = secrets.token_bytes(32)

supabase: Client | None = None
if SUPABASE_URL and SUPABASE_SERVICE_ROLE_KEY:
    try:
        supabase = create_client(SUPABASE_URL, SUPABASE_SERVICE_ROLE_KEY)
    except Exception:
        logging.exception("Supabase client initialization failed")
        supabase = None

DAILY_LIMIT = max(1, _int_env("DAILY_LIMIT", 15))
MONTHLY_LIMIT = max(1, _int_env("MONTHLY_LIMIT", 475))
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")
COOLDOWN_SECONDS = max(0, _int_env("COOLDOWN_SECONDS", 30))


@dataclass
class MemoryQuotaRecord:
    daily_period: str
    daily_count: int
    monthly_period: str
    monthly_count: int
    last_request_at: float | None
    touched_at: float


memory_quota_by_client: dict[str, MemoryQuotaRecord] = {}
memory_quota_lock = threading.Lock()


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _period_keys(now: float) -> tuple[str, str]:
    current = datetime.fromtimestamp(now, timezone.utc)
    return current.strftime("%Y-%m-%d"), current.strftime("%Y-%m")


def _seconds_until_next_day(now: float) -> int:
    current = datetime.fromtimestamp(now, timezone.utc)
    next_day = (current + timedelta(days=1)).replace(hour=0, minute=0, second=0, microsecond=0)
    return max(1, int((next_day - current).total_seconds() + 0.999999))


def _seconds_until_next_month(now: float) -> int:
    current = datetime.fromtimestamp(now, timezone.utc)
    if current.month == 12:
        next_month = datetime(current.year + 1, 1, 1, tzinfo=timezone.utc)
    else:
        next_month = datetime(current.year, current.month + 1, 1, tzinfo=timezone.utc)
    return max(1, int((next_month - current).total_seconds() + 0.999999))


def _rate_limited_decision(error_code: str, error: str, retry_after: int) -> dict:
    return {
        "blocked": True,
        "status_code": 429,
        "payload": {
            "status": "rate_limited",
            "error_code": error_code,
            "error": error,
            "retry_after_seconds": max(1, int(retry_after)),
        },
    }


def _purge_memory_quota(now: float) -> None:
    cutoff = now - MEMORY_LIMITER_TTL_SECONDS
    expired = [key for key, record in memory_quota_by_client.items() if record.touched_at < cutoff]
    for key in expired:
        memory_quota_by_client.pop(key, None)
    if len(memory_quota_by_client) > MEMORY_LIMITER_MAX_ENTRIES:
        oldest = sorted(
            memory_quota_by_client,
            key=lambda key: memory_quota_by_client[key].touched_at,
        )[: len(memory_quota_by_client) - MEMORY_LIMITER_MAX_ENTRIES]
        for key in oldest:
            memory_quota_by_client.pop(key, None)


def _memory_quota_decision(client_id_hash: str, *, consume: bool) -> dict:
    now = time.time()
    today, month = _period_keys(now)
    with memory_quota_lock:
        _purge_memory_quota(now)
        record = memory_quota_by_client.get(client_id_hash)
        if record is None:
            daily_count = 0
            monthly_count = 0
            last_request_at = None
        else:
            daily_count = record.daily_count if record.daily_period == today else 0
            monthly_count = record.monthly_count if record.monthly_period == month else 0
            last_request_at = record.last_request_at

        if last_request_at is not None and now - last_request_at < COOLDOWN_SECONDS:
            return _rate_limited_decision(
                "cooldown",
                "Please wait before trying again.",
                COOLDOWN_SECONDS - (now - last_request_at),
            )
        if daily_count >= DAILY_LIMIT:
            return _rate_limited_decision(
                "daily_limit",
                "Daily recognition limit reached.",
                _seconds_until_next_day(now),
            )
        if monthly_count >= MONTHLY_LIMIT:
            return _rate_limited_decision(
                "monthly_limit",
                "Monthly recognition limit reached.",
                _seconds_until_next_month(now),
            )
        if consume:
            memory_quota_by_client[client_id_hash] = MemoryQuotaRecord(
                daily_period=today,
                daily_count=daily_count + 1,
                monthly_period=month,
                monthly_count=monthly_count + 1,
                last_request_at=now,
                touched_at=now,
            )
        return {"blocked": False}


def _production_quota_configured() -> bool:
    return bool(
        SUPABASE_URL
        and SUPABASE_SERVICE_ROLE_KEY
        and CLIENT_ID_HMAC_SECRET
        and supabase is not None
    )


def _quota_mode() -> str:
    if APP_ENV == "development":
        return "development-memory"
    if _production_quota_configured():
        return "production"
    return "unavailable"


def _get_client_ip() -> str:
    remote_addr = request.remote_addr or "unknown"
    if TRUSTED_PROXY_COUNT <= 0 or remote_addr not in TRUSTED_PROXY_IPS:
        return remote_addr
    forwarded = [
        part.strip()
        for part in request.headers.get("X-Forwarded-For", "").split(",")
        if part.strip()
    ]
    if len(forwarded) < TRUSTED_PROXY_COUNT:
        return remote_addr
    # REMOTE_ADDR is the immediate proxy. For N trusted hops, the N-1
    # right-most forwarded values must also be explicitly trusted proxies.
    trusted_forwarded_hops = (
        forwarded[-(TRUSTED_PROXY_COUNT - 1) :] if TRUSTED_PROXY_COUNT > 1 else []
    )
    if any(address not in TRUSTED_PROXY_IPS for address in trusted_forwarded_hops):
        return remote_addr
    client_address = forwarded[-TRUSTED_PROXY_COUNT]
    try:
        ipaddress.ip_address(client_address)
    except ValueError:
        return remote_addr
    return client_address


def _client_id_hash() -> str:
    secret = (
        CLIENT_ID_HMAC_SECRET.encode("utf-8") if CLIENT_ID_HMAC_SECRET else _DEVELOPMENT_HMAC_SECRET
    )
    return hmac.new(secret, _get_client_ip().encode("utf-8"), hashlib.sha256).hexdigest()


def _check_rate_limits(client_id_hash: str) -> dict:
    """Perform a non-consuming check before accepting upload work."""
    if APP_ENV == "development":
        return _memory_quota_decision(client_id_hash, consume=False)
    if not _production_quota_configured():
        return {"service_error": True}
    try:
        response = supabase.rpc(
            "check_api_quota",
            {
                "p_client_id_hash": client_id_hash,
                "p_daily_limit": DAILY_LIMIT,
                "p_monthly_limit": MONTHLY_LIMIT,
                "p_cooldown_seconds": COOLDOWN_SECONDS,
                "p_now": _utc_now().isoformat(),
            },
        ).execute()
        data = response.data
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict) or "allowed" not in data:
            raise RuntimeError("quota preflight returned an invalid response")
        if data["allowed"]:
            return {"blocked": False}
        return _quota_limit_decision(data)
    except Exception:
        logging.exception("Supabase quota preflight failed")
        return {"service_error": True}


def _quota_limit_decision(data: dict) -> dict:
    reason = str(data.get("reason", "quota_limit"))
    if reason == "cooldown":
        error = "Please wait before trying again."
    elif reason == "daily_limit":
        error = "Daily recognition limit reached."
    else:
        reason = "monthly_limit" if reason == "monthly_limit" else "quota_limit"
        error = (
            "Monthly recognition limit reached."
            if reason == "monthly_limit"
            else "Recognition quota reached."
        )
    return _rate_limited_decision(reason, error, int(data.get("retry_after_seconds", 1)))


def _consume_quota(client_id_hash: str) -> dict:
    if APP_ENV == "development":
        return _memory_quota_decision(client_id_hash, consume=True)
    if not _production_quota_configured():
        return {"service_error": True}
    try:
        response = supabase.rpc(
            "consume_api_quota",
            {
                "p_client_id_hash": client_id_hash,
                "p_daily_limit": DAILY_LIMIT,
                "p_monthly_limit": MONTHLY_LIMIT,
                "p_cooldown_seconds": COOLDOWN_SECONDS,
                "p_now": _utc_now().isoformat(),
            },
        ).execute()
        data = response.data
        if isinstance(data, list):
            data = data[0] if data else None
        if not isinstance(data, dict) or "allowed" not in data:
            raise RuntimeError("quota RPC returned an invalid response")
        if data["allowed"]:
            return {"blocked": False}
        return _quota_limit_decision(data)
    except Exception:
        logging.exception("Supabase quota RPC failed")
        return {"service_error": True}


def _file_size(upload) -> int | None:
    stream = getattr(upload, "stream", None)
    if stream is None or not hasattr(stream, "seek"):
        return None
    try:
        current = stream.tell()
        stream.seek(0, os.SEEK_END)
        size = int(stream.tell())
        stream.seek(current)
        return size
    except (OSError, ValueError):
        return None


def _load_web_upload(upload, config: AppConfig):
    filename = (getattr(upload, "filename", None) or "upload.wav").strip()
    suffix = Path(filename).suffix.lower() or ".wav"
    if suffix not in SUPPORTED_WEB_SUFFIXES:
        raise AudioInputError("unsupported_format", "This web upload format is not supported.")
    size = _file_size(upload)
    if size is not None and size > config.max_upload_bytes:
        raise AudioInputError("upload_too_large", "Audio file exceeds the upload size limit.")

    input_handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    input_handle.close()
    converted_path: Path | None = None
    try:
        upload.save(input_handle.name)
        input_path = Path(input_handle.name)
        if input_path.stat().st_size > config.max_upload_bytes:
            raise AudioInputError("upload_too_large", "Audio file exceeds the upload size limit.")
        wav_path = input_path
        if suffix != ".wav":
            converted_handle = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
            converted_handle.close()
            converted_path = Path(converted_handle.name)
            convert_with_ffmpeg(
                input_path,
                converted_path,
                sample_rate=config.internal_sample_rate,
                timeout=config.ffmpeg_timeout_seconds,
            )
            wav_path = converted_path
        return load_audio_file(wav_path, config=config, max_bytes=config.max_upload_bytes)
    finally:
        try:
            Path(input_handle.name).unlink(missing_ok=True)
        except OSError:
            pass
        if converted_path is not None:
            try:
                converted_path.unlink(missing_ok=True)
            except OSError:
                pass


def _audio_error_response(exc: AudioInputError):
    status_code = 413 if exc.code in {"upload_too_large", "too_long"} else 400
    return jsonify(
        {"status": "invalid_audio", "error_code": exc.code, "error": exc.message}
    ), status_code


def _quota_unavailable_response():
    return jsonify(
        {
            "status": "error",
            "error_code": "quota_unavailable",
            "error": "Production quota service is unavailable.",
        }
    ), 503


def _rate_limit_response(decision: dict):
    payload = decision["payload"]
    retry_after = max(1, int(payload.get("retry_after_seconds", 1)))
    payload.setdefault("retry_after_seconds", retry_after)
    return (
        jsonify(payload),
        decision["status_code"],
        {
            "Retry-After": str(retry_after),
        },
    )


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/match", methods=["POST"])
def api_match():
    if INTERNAL_API_SECRET and request.headers.get("X-API-Secret") != INTERNAL_API_SECRET:
        return jsonify(
            {"status": "error", "error_code": "unauthorized", "error": "Unauthorized."}
        ), 401
    if _quota_mode() == "unavailable":
        return _quota_unavailable_response()
    if "file" not in request.files:
        return jsonify(
            {
                "status": "invalid_audio",
                "error_code": "missing_upload",
                "error": "No audio file was uploaded.",
            }
        ), 400

    client_id_hash = _client_id_hash()
    limit_check = _check_rate_limits(client_id_hash)
    if limit_check.get("service_error"):
        return _quota_unavailable_response()
    if limit_check["blocked"]:
        return _rate_limit_response(limit_check)

    config = load_config()
    try:
        clip = _load_web_upload(request.files["file"], config)
    except AudioInputError as exc:
        return _audio_error_response(exc)
    except Exception:
        return jsonify(
            {
                "status": "error",
                "error_code": "upload_failed",
                "error": "Audio upload could not be processed.",
            }
        ), 400

    quota_result = _consume_quota(client_id_hash)
    if quota_result.get("service_error"):
        return _quota_unavailable_response()
    if quota_result["blocked"]:
        return _rate_limit_response(quota_result)
    try:
        return jsonify(matcher.match_audio(clip, config))
    except Exception:
        return jsonify(
            {"status": "error", "error_code": "internal_error", "error": "Recognition failed."}
        ), 500


@app.errorhandler(413)
def request_entity_too_large(_error):
    return jsonify(
        {
            "status": "invalid_audio",
            "error_code": "upload_too_large",
            "error": "Audio file exceeds the upload size limit.",
        }
    ), 413


@app.route("/api/status", methods=["GET"])
def api_status():
    config = load_config()
    fpcalc_path_exists = bool(config.fpcalc_path and Path(config.fpcalc_path).exists())
    quota_mode = _quota_mode()
    body = {
        "status": "ok" if quota_mode != "unavailable" else "error",
        "supabase_configured": _production_quota_configured(),
        "quota_mode": quota_mode,
        "production_grade_quotas_enabled": quota_mode == "production",
        "rapidapi_configured": bool(config.rapidapi_key),
        "acoustid_configured": bool(config.acoustid_api_key),
        "audd_configured": bool(config.audd_api_token),
        "local_index_configured": bool(config.fingerprint_index_path),
        "fpcalc_on_path": bool(shutil.which("fpcalc")),
        "fpcalc_path_exists": fpcalc_path_exists,
        "ffmpeg_on_path": bool(shutil.which("ffmpeg")),
        "supported_formats": list(SUPPORTED_WEB_FORMATS),
        "internal_sample_rate": config.internal_sample_rate,
        "min_audio_seconds": config.min_audio_seconds,
        "max_audio_seconds": config.max_audio_seconds,
        "max_upload_bytes": config.max_upload_bytes,
        "daily_limit": DAILY_LIMIT,
        "monthly_limit": MONTHLY_LIMIT,
        "cooldown_seconds": COOLDOWN_SECONDS,
        "trusted_proxy_count": TRUSTED_PROXY_COUNT,
    }
    if quota_mode == "unavailable":
        body.update(
            {
                "error_code": "quota_unavailable",
                "error": "Production quota service is unavailable.",
            }
        )
        return jsonify(body), 503
    return jsonify(body)


if __name__ == "__main__":
    app.run(
        host="127.0.0.1",
        port=5000,
        debug=APP_ENV == "development" and os.getenv("FLASK_DEBUG", "0") == "1",
    )
