from __future__ import annotations

from pathlib import Path
import tempfile
import wave
import os
import subprocess
import json
import shutil
import logging
import requests
from typing import Any
import base64

import numpy as np

from recorder import AudioClip
from config import AppConfig


AUDD_ENDPOINT = "https://api.audd.io/"
ACOUSTID_ENDPOINT = "https://api.acoustid.org/v2/lookup"


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


def match_audio(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    # Try Shazam (RapidAPI) first — most accurate
    if config.rapidapi_key:
        try:
            return match_audio_shazam(clip, config, timeout=timeout)
        except Exception:
            pass

    # Fall back to AcoustID
    if config.acoustid_api_key:
        try:
            return match_audio_acoustid(clip, config, timeout=timeout)
        except Exception:
            pass

    if not config.audd_api_token:
        return {"status": "no_token"}

    # write clip to temp file
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
            return {"status": "error", "error": f"HTTP {resp.status_code}"}

        body = resp.json()
        res = body.get("result")
        if not res:
            return {"status": "no_match", "result": None}

        title = res.get("title") or res.get("song") or ""
        artist = res.get("artist") or ""
        album = res.get("album") or ""

        def _extract_image(body: dict) -> str | None:
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

        image = _extract_image(res)

        return {
            "status": "matched",
            "result": res,
            "title": title,
            "artist": artist,
            "album": album,
            "image": image,
        }

    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass


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
            return {"status": "error", "error": "fpcalc not found; install Chromaprint or set FP_CALC_PATH in .env"}

        fpcalc_cmd = [fpcalc_exe, str(tmp.name)]
        proc = subprocess.run(fpcalc_cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            logging.error("fpcalc failed: %s", proc.stderr.strip())
            raise RuntimeError(f"fpcalc failed: {proc.stderr.strip()}")

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
            return {"status": "error", "error": "Could not obtain fingerprint from fpcalc"}

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
            return {"status": "error", "error": f"HTTP {resp.status_code}"}

        body = resp.json()
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

    except Exception as exc:
        return {"status": "error", "error": str(exc)}
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
        _write_clip_to_wav(clip, Path(tmp.name))

        with open(tmp.name, "rb") as f:
            audio_data = base64.b64encode(f.read()).decode("utf-8")

        headers = {
            "content-type": "text/plain",
            "X-RapidAPI-Key": config.rapidapi_key,
            "X-RapidAPI-Host": "shazam.p.rapidapi.com"
        }

        resp = requests.post(
            "https://shazam.p.rapidapi.com/songs/detect",
            headers=headers,
            data=audio_data,
            timeout=timeout
        )

        if resp.status_code != 200:
            return {"status": "error", "error": f"HTTP {resp.status_code}"}

        body = resp.json()

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

    except Exception as exc:
        return {"status": "error", "error": str(exc)}
    finally:
        try:
            os.unlink(tmp.name)
        except Exception:
            pass