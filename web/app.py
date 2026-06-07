from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from flask_cors import CORS
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request
from supabase import create_client, Client

from shazam_project import matcher
from shazam_project.config import load_config
from shazam_project.recorder import load_audio_file

app = Flask(__name__, template_folder="templates", static_folder="static")
CORS(app, origins=["http://localhost:5173"])

# --- Config from env vars ---
SUPABASE_URL = os.getenv("SUPABASE_URL", "")
SUPABASE_KEY = os.getenv("SUPABASE_KEY", "")
DAILY_LIMIT = int(os.getenv("DAILY_LIMIT", "15"))
MONTHLY_LIMIT = int(os.getenv("MONTHLY_LIMIT", "475"))
INTERNAL_API_SECRET = os.getenv("INTERNAL_API_SECRET", "")
COOLDOWN_SECONDS = 30

supabase: Client = create_client(SUPABASE_URL, SUPABASE_KEY)

last_request_by_ip: dict[str, float] = {}


# --- Helpers ---

def _safe_unlink(path: str | None) -> None:
    if not path:
        return
    try:
        if os.path.exists(path):
            os.unlink(path)
    except Exception:
        pass


def _utc_now() -> datetime:
    return datetime.now(timezone.utc)


def _today_key() -> str:
    return "daily:" + _utc_now().strftime("%Y-%m-%d")


def _month_key() -> str:
    return "monthly:" + _utc_now().strftime("%Y-%m")


def _get_count(key: str) -> int:
    try:
        res = supabase.table("api_usage").select("call_count").eq("key", key).execute()
        if res.data:
            row = res.data[0]
            if isinstance(row, dict):
                return int(row.get("call_count", 0))  # type: ignore
        return 0
    except Exception:
        return 0


# NEW — atomic, no race condition
def _increment_count(key: str) -> None:
    try:
        supabase.rpc("increment_api_usage", {"p_key": key}).execute()
    except Exception:
        pass


TRUSTED_PROXIES = {"127.0.0.1", "::1"}  # add your reverse proxy IP if deploying

def _get_client_ip() -> str:
    if request.remote_addr in TRUSTED_PROXIES:
        forwarded = request.headers.get("X-Forwarded-For", "")
        if forwarded:
            return forwarded.split(",")[0].strip()
    return request.remote_addr or "unknown"


def _check_rate_limits(ip: str) -> dict:
    now = time.time()

    last_seen = last_request_by_ip.get(ip)
    if last_seen is not None:
        remaining = COOLDOWN_SECONDS - (now - last_seen)
        if remaining > 0:
            return {
                "blocked": True,
                "status_code": 429,
                "payload": {
                    "status": "rate_limited",
                    "error": f"Please wait {int(remaining) + 1} seconds before trying again."
                }
            }

    today = _today_key()
    month = _month_key()

    daily_count = _get_count(today)
    monthly_count = _get_count(month)

    if daily_count >= DAILY_LIMIT:
        return {
            "blocked": True,
            "status_code": 429,
            "payload": {
                "status": "rate_limited",
                "error": "Daily recognition limit reached. Please try again tomorrow."
            }
        }

    if monthly_count >= MONTHLY_LIMIT:
        return {
            "blocked": True,
            "status_code": 429,
            "payload": {
                "status": "rate_limited",
                "error": "Monthly recognition limit reached. Recognition is temporarily disabled."
            }
        }

    return {
        "blocked": False,
        "today": today,
        "month": month,
        "now": now,
    }


def _record_request(ip: str, today: str, month: str, now: float) -> None:
    last_request_by_ip[ip] = now
    _increment_count(today)
    _increment_count(month)


# --- Routes ---

@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/match", methods=["POST"])
def api_match():
    # Secret header check
    if INTERNAL_API_SECRET and request.headers.get("X-API-Secret") != INTERNAL_API_SECRET:
        return jsonify({"status": "error", "error": "Unauthorized"}), 401

    cfg = load_config()

    if "file" not in request.files:
        return jsonify({"status": "error", "error": "No file uploaded"}), 400

    ip = _get_client_ip()
    limit_check = _check_rate_limits(ip)
    if limit_check["blocked"]:
        return jsonify(limit_check["payload"]), limit_check["status_code"]

    f = request.files["file"]
    filename = getattr(f, "filename", None) or "upload"
    suffix = os.path.splitext(filename)[1] or ""
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    wav_path = None

    try:
        f.save(tmp.name)
        tmp.close()

        wav_path = tmp.name
        if not tmp.name.lower().endswith(".wav"):
            ffmpeg_exe = shutil.which("ffmpeg")
            if ffmpeg_exe:
                conv_tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
                conv_tmp.close()
                try:
                    cmd = [ffmpeg_exe, "-y", "-i", tmp.name, "-ar", "44100", "-ac", "1", conv_tmp.name]
                    subprocess.run(cmd, check=True, capture_output=True)
                    wav_path = conv_tmp.name
                except subprocess.CalledProcessError:
                    wav_path = tmp.name
            else:
                wav_path = tmp.name

        try:
            clip = load_audio_file(wav_path)
        except Exception as e:
            return jsonify({"status": "error", "error": f"Failed to load audio: {e}"}), 400

        _record_request(ip, limit_check["today"], limit_check["month"], limit_check["now"])

        result = matcher.match_audio(clip, cfg)
        return jsonify(result)

    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        tmp_name = getattr(tmp, "name", None) if "tmp" in locals() else None
        _safe_unlink(tmp_name)
        if wav_path != tmp_name:
            _safe_unlink(wav_path)


@app.route("/api/status", methods=["GET"])
def api_status():
    cfg = load_config()
    acoustid_configured = bool(cfg.acoustid_api_key)
    audd_configured = bool(cfg.audd_api_token)

    fpcalc_on_path = shutil.which("fpcalc") is not None
    fpcalc_path_exists = False
    if cfg.fpcalc_path:
        try:
            fpcalc_path_exists = os.path.exists(cfg.fpcalc_path)
        except Exception:
            fpcalc_path_exists = False

    ffmpeg_on_path = shutil.which("ffmpeg") is not None

    today = _today_key()
    month = _month_key()

    return jsonify(
        {
            "acoustid_configured": acoustid_configured,
            "audd_configured": audd_configured,
            "fpcalc_on_path": fpcalc_on_path,
            "fpcalc_path_exists": fpcalc_path_exists,
            "ffmpeg_on_path": ffmpeg_on_path,
            "daily_used": _get_count(today),
            "daily_limit": DAILY_LIMIT,
            "monthly_used": _get_count(month),
            "monthly_limit": MONTHLY_LIMIT,
            "cooldown_seconds": COOLDOWN_SECONDS,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)