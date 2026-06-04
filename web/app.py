from __future__ import annotations

import json
import os
import shutil
import subprocess
import tempfile
import time
from datetime import datetime, timezone
from pathlib import Path

from flask import Flask, jsonify, render_template, request

from shazam_project import matcher
from shazam_project.config import load_config
from shazam_project.recorder import load_audio_file

app = Flask(__name__, template_folder="templates", static_folder="static")

RATE_LIMIT_FILE = Path("artifacts/rate_limit_usage.json")
COOLDOWN_SECONDS = 30
DAILY_LIMIT = 12
MONTHLY_LIMIT = 450

last_request_by_ip: dict[str, float] = {}


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
    return _utc_now().strftime("%Y-%m-%d")


def _month_key() -> str:
    return _utc_now().strftime("%Y-%m")


def _load_usage() -> dict:
    if not RATE_LIMIT_FILE.exists():
        return {"daily": {}, "monthly": {}}
    try:
        return json.loads(RATE_LIMIT_FILE.read_text(encoding="utf-8"))
    except Exception:
        return {"daily": {}, "monthly": {}}


def _save_usage(data: dict) -> None:
    RATE_LIMIT_FILE.parent.mkdir(parents=True, exist_ok=True)
    RATE_LIMIT_FILE.write_text(json.dumps(data, indent=2), encoding="utf-8")


def _get_client_ip() -> str:
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

    usage = _load_usage()
    today = _today_key()
    month = _month_key()

    daily_count = usage["daily"].get(today, 0)
    monthly_count = usage["monthly"].get(month, 0)

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
        "usage": usage,
        "today": today,
        "month": month,
        "now": now,
    }


def _record_request(ip: str, usage: dict, today: str, month: str, now: float) -> None:
    last_request_by_ip[ip] = now
    usage["daily"][today] = usage["daily"].get(today, 0) + 1
    usage["monthly"][month] = usage["monthly"].get(month, 0) + 1
    _save_usage(usage)


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/match", methods=["POST"])
def api_match():
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

        _record_request(
            ip,
            limit_check["usage"],
            limit_check["today"],
            limit_check["month"],
            limit_check["now"],
        )

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

    usage = _load_usage()
    today = _today_key()
    month = _month_key()

    return jsonify(
        {
            "acoustid_configured": acoustid_configured,
            "audd_configured": audd_configured,
            "fpcalc_on_path": fpcalc_on_path,
            "fpcalc_path_exists": fpcalc_path_exists,
            "ffmpeg_on_path": ffmpeg_on_path,
            "daily_used": usage["daily"].get(today, 0),
            "daily_limit": DAILY_LIMIT,
            "monthly_used": usage["monthly"].get(month, 0),
            "monthly_limit": MONTHLY_LIMIT,
            "cooldown_seconds": COOLDOWN_SECONDS,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)