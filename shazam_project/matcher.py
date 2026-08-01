from __future__ import annotations

import base64
import json
import logging
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Any
import wave

import numpy as np
import requests

from .config import AppConfig
from .fingerprint import match_local_index
from .recorder import AudioClip, AudioInputError, normalize_audio


AUDD_ENDPOINT = "https://api.audd.io/"
ACOUSTID_ENDPOINT = "https://api.acoustid.org/v2/lookup"


SAFE_ERROR_MESSAGES = {
    "configuration_error": "Recognition provider is not configured correctly.",
    "fpcalc_error": "Acoustic fingerprint generation failed.",
    "fpcalc_output_error": "Acoustic fingerprint generation returned no fingerprint.",
    "http_error": "Recognition provider returned an HTTP error.",
    "local_match_error": "Local fingerprint matching failed.",
    "malformed_response": "Recognition provider returned an invalid response.",
    "provider_error": "Recognition provider failed.",
    "request_error": "Recognition provider request failed.",
    "timeout": "Recognition provider timed out.",
}


def _error_response(error_code: str, detail: str | None = None) -> dict[str, Any]:
    """Return a stable public error without exposing provider diagnostics."""
    del detail
    return {
        "status": "error",
        "error_code": error_code,
        "error": SAFE_ERROR_MESSAGES.get(error_code, SAFE_ERROR_MESSAGES["provider_error"]),
    }


def _write_clip_to_wav(clip: AudioClip, path: Path) -> None:
    """Write a float32 mono AudioClip to a 16-bit PCM WAV file."""
    samples = np.asarray(clip.samples, dtype=np.float32)
    samples = np.clip(samples, -1.0, 1.0)
    int16 = (samples * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(clip.sample_rate))
        wf.writeframes(int16.tobytes())


def _extract_audd_image(body: dict[str, Any]) -> str | None:
    img = body.get("album_cover")
    if img:
        return img

    spotify = body.get("spotify") or {}
    if isinstance(spotify, dict):
        album_obj = spotify.get("album")
        if isinstance(album_obj, dict):
            images = album_obj.get("images") or []
            if images and isinstance(images, list):
                first = images[0]
                if isinstance(first, dict):
                    return first.get("url")
    return None


def _match_audio_audd(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Match a clip with AudD and return the shared result shape."""
    if not config.audd_api_token:
        logging.debug("AudD API token not configured")
        return {"status": "no_token"}
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    try:
        _write_clip_to_wav(clip, Path(tmp.name))

        files = {"file": open(tmp.name, "rb")}
        data = {"api_token": config.audd_api_token}
        try:
            resp = requests.post(AUDD_ENDPOINT, files=files, data=data, timeout=timeout)
        finally:
            files["file"].close()

        if resp.status_code != 200:
            logging.warning("AudD returned HTTP status %s", resp.status_code)
            return _error_response("http_error")

        try:
            body = resp.json()
        except (TypeError, ValueError):
            logging.exception("AudD returned invalid JSON")
            return _error_response("malformed_response")
        res = body.get("result")
        if not res:
            return {"status": "no_match", "result": None}

        title = res.get("title") or res.get("song") or ""
        artist = res.get("artist") or ""
        album = res.get("album") or ""

        image = _extract_audd_image(res)

        return {
            "status": "matched",
            "result": res,
            "title": title,
            "artist": artist,
            "album": album,
            "image": image,
        }

    except requests.Timeout:
        logging.exception("AudD request timed out")
        return _error_response("timeout")
    except requests.RequestException:
        logging.exception("AudD request failed")
        return _error_response("request_error")
    except Exception:
        logging.exception("AudD provider failed")
        return _error_response("provider_error")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def _attempt_summary(backend: str, response: dict[str, Any]) -> dict[str, Any]:
    """Return safe diagnostics without copying provider payloads or secrets."""
    summary = {
        "backend": backend,
        "status": response.get("status", "error"),
    }
    if response.get("error"):
        summary["error"] = response["error"]
    if response.get("error_code"):
        summary["error_code"] = response["error_code"]
    return summary


def _public_response(response: dict[str, Any]) -> dict[str, Any]:
    """Keep provider payloads and local paths out of the public contract."""
    allowed = {
        "status", "error_code", "error", "title", "artist", "album", "genre",
        "image", "score", "votes", "fingerprint_hashes", "matched_hashes",
        "offset_frames", "backend", "attempts",
    }
    public = {key: value for key, value in response.items() if key in allowed and value is not None}
    if response.get("status") == "error":
        code = response.get("error_code", "provider_error")
        public["error_code"] = code
        public["error"] = SAFE_ERROR_MESSAGES.get(code, SAFE_ERROR_MESSAGES["provider_error"])
    if response.get("status") == "no_match":
        public.pop("error", None)
        public.pop("error_code", None)
        public["result"] = None
    return public


def match_audio(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Normalize once, then try every backend in the documented fallback order."""
    try:
        normalized = normalize_audio(
            clip.samples,
            clip.sample_rate,
            source=clip.source,
            target_sample_rate=config.internal_sample_rate,
            min_audio_seconds=config.min_audio_seconds,
            max_audio_seconds=config.max_audio_seconds,
            path=clip.path,
        )
    except AudioInputError as exc:
        return {"status": "invalid_audio", "error_code": exc.code, "error": exc.message}

    providers: list[tuple[str, Any]] = [
        ("rapidapi", match_audio_shazam),
        ("acoustid", match_audio_acoustid),
        ("audd", _match_audio_audd),
        ("local", match_audio_local),
    ]

    attempts: list[dict[str, Any]] = []
    last_response: dict[str, Any] = {"status": "error", "error": "No provider response"}

    for backend, provider in providers:
        try:
            response = dict(provider(normalized, config, timeout=timeout))
        except Exception:
            logging.exception("%s provider failed", backend)
            response = _error_response("provider_error")

        if response.get("status") == "no_token":
            response = {
                "status": "not_configured",
                "error_code": f"{backend}_not_configured",
                "error": f"{backend} is not configured.",
            }
        response = _public_response(response)
        response["backend"] = backend
        attempts.append(_attempt_summary(backend, response))
        last_response = response

        if response.get("status") == "matched":
            response["attempts"] = attempts
            return response

        if response.get("status") not in {"error", "no_match", "no_token", "not_configured"}:
            response["attempts"] = attempts
            return response

    if all(item["status"] == "not_configured" for item in attempts):
        return {
            "status": "not_configured",
            "error_code": "no_backend_configured",
            "error": "No recognition provider is configured.",
            "attempts": attempts,
        }
    last_response["attempts"] = attempts
    return last_response


def match_audio_acoustid(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Fingerprint audio with `fpcalc` and query AcoustID."""
    if not config.acoustid_api_key:
        logging.debug("AcoustID API key not configured")
        return {"status": "no_token"}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    try:
        _write_clip_to_wav(clip, Path(tmp.name))

        fpcalc_exe = None
        if config.fpcalc_path:
            fpcalc_exe = config.fpcalc_path
        else:
            fpcalc_exe = shutil.which("fpcalc")

        if not fpcalc_exe:
            logging.error("fpcalc not found; install Chromaprint or set FP_CALC_PATH in .env")
            return _error_response("configuration_error")

        fpcalc_cmd = [fpcalc_exe, str(tmp.name)]
        proc = subprocess.run(fpcalc_cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            logging.error("fpcalc failed: %s", proc.stderr.strip())
            return _error_response("fpcalc_error")

        fingerprint = None
        duration = None
        for line in proc.stdout.splitlines():
            if line.startswith("FINGERPRINT="):
                fingerprint = line.split("=", 1)[1].strip()
            if line.startswith("DURATION="):
                duration = line.split("=", 1)[1].strip()

        if not fingerprint or not duration:
            try:
                data = json.loads(proc.stdout)
                fingerprint = fingerprint or data.get("fingerprint")
                duration = duration or str(data.get("duration"))
            except Exception:
                pass

        if not fingerprint or not duration:
            logging.error("Could not obtain fingerprint from fpcalc")
            return _error_response("fpcalc_output_error", "Could not obtain fingerprint from fpcalc")

        params = {
            "client": config.acoustid_api_key,
            "fingerprint": fingerprint,
            "duration": duration,
            "format": "json",
            "meta": "recordings+releasegroups+artists",
        }

        resp = requests.get(ACOUSTID_ENDPOINT, params=params, timeout=timeout)
        if resp.status_code != 200:
            logging.error("AcoustID HTTP error: %s", resp.status_code)
            return _error_response("http_error")

        try:
            body = resp.json()
        except (TypeError, ValueError):
            logging.exception("AcoustID returned invalid JSON")
            return _error_response("malformed_response")
        results = body.get("results") or []
        if not results:
            logging.info("AcoustID returned no match")
            return {"status": "no_match", "result": None}

        best = results[0]
        title = None
        artist = None
        album = None

        if "recordings" in best and best["recordings"]:
            rec = best["recordings"][0]
            title = rec.get("title")
            if rec.get("artists"):
                artist = ", ".join(a.get("name") for a in rec.get("artists") if a.get("name"))
            if rec.get("releasegroups"):
                album = rec.get("releasegroups")[0].get("title")

        title = title or ""
        artist = artist or ""
        album = album or ""

        logging.info("AcoustID matched: %s - %s", artist, title)
        return {
            "status": "matched",
            "result": best,
            "title": title,
            "artist": artist,
            "album": album,
            "image": None,
        }

    except subprocess.TimeoutExpired:
        logging.exception("AcoustID fingerprinting timed out")
        return _error_response("timeout")
    except requests.Timeout:
        logging.exception("AcoustID request timed out")
        return _error_response("timeout")
    except requests.RequestException:
        logging.exception("AcoustID request failed")
        return _error_response("request_error")
    except Exception:
        logging.exception("AcoustID provider failed")
        return _error_response("provider_error")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def match_audio_shazam(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Fingerprint audio using RapidAPI Shazam endpoint."""
    if not config.rapidapi_key:
        return {"status": "no_token"}

    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    try:
        max_samples = 5 * clip.sample_rate
        trimmed = AudioClip(
            samples=clip.samples[:max_samples],
            sample_rate=clip.sample_rate,
            source=clip.source,
        )
        _write_clip_to_wav(trimmed, Path(tmp.name))

        with open(tmp.name, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "content-type": "text/plain",
            "X-RapidAPI-Key": config.rapidapi_key,
            "X-RapidAPI-Host": "shazam.p.rapidapi.com",
        }

        resp = requests.post(
            "https://shazam.p.rapidapi.com/songs/detect",
            headers=headers,
            data=audio_data,
            timeout=timeout,
        )

        if resp.status_code != 200:
            logging.warning("RapidAPI returned HTTP status %s", resp.status_code)
            return _error_response("http_error")

        try:
            body = resp.json()
        except (TypeError, ValueError):
            logging.exception("RapidAPI returned invalid JSON")
            return _error_response("malformed_response")

        track = body.get("track")
        if not track:
            return {"status": "no_match", "result": None}

        title = track.get("title", "")
        artist = track.get("subtitle", "")
        album = ""
        image = track.get("images", {}).get("coverarthq") or track.get("images", {}).get("coverart")

        sections = track.get("sections", [])
        for section in sections:
            if section.get("type") == "SONG":
                for meta in section.get("metadata", []):
                    if meta.get("title") == "Album":
                        album = meta.get("text", "")

        return {
            "status": "matched",
            "result": track,
            "title": title,
            "artist": artist,
            "album": album,
            "image": image,
        }

    except requests.Timeout:
        logging.exception("RapidAPI request timed out")
        return _error_response("timeout")
    except requests.RequestException:
        logging.exception("RapidAPI request failed")
        return _error_response("request_error")
    except Exception:
        logging.exception("RapidAPI provider failed")
        return _error_response("provider_error")
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


def match_audio_local(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Match a clip against the local constellation-hash index."""
    del timeout  # the local matcher is CPU-bound and does not make network calls
    if not config.fingerprint_index_path:
        return {"status": "no_token"}
    try:
        return _public_response(match_local_index(clip, config.fingerprint_index_path))
    except Exception:
        logging.exception("Local fingerprint matching failed")
        return _error_response("local_match_error")
