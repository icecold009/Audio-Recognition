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

import numpy as np

from recorder import AudioClip
from config import AppConfig


AUDD_ENDPOINT = "https://api.audd.io/"
ACOUSTID_ENDPOINT = "https://api.acoustid.org/v2/lookup"


def _write_clip_to_wav(clip: AudioClip, path: Path) -> None:
    """Write a float32 mono AudioClip to a 16-bit PCM WAV file."""
    samples = np.asarray(clip.samples, dtype=np.float32)
    # clip into [-1.0, 1.0]
    samples = np.clip(samples, -1.0, 1.0)
    int16 = (samples * 32767.0).astype(np.int16)

    with wave.open(str(path), "wb") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(int(clip.sample_rate))
        wf.writeframes(int16.tobytes())


def match_audio(clip: AudioClip, config: AppConfig, timeout: int = 15) -> dict[str, Any]:
    """Send audio to AudD and return a normalized result dict.

    Returns a dict with keys:
    - status: 'no_token', 'error', 'no_match', 'matched'
    - error: optional error message
    - result: raw API result when matched
    - title, artist, album, image: when available
    """
    # Prefer AcoustID if configured (uses local `fpcalc` to fingerprint)
    if config.acoustid_api_key:
        try:
            return match_audio_acoustid(clip, config, timeout=timeout)
        except Exception:
            # fall back to AudD on any failure
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
        # AudD returns 'result' key; if None, no match
        res = body.get("result")
        if not res:
            return {"status": "no_match", "result": None}

        title = res.get("title") or res.get("song") or None
        artist = res.get("artist") or None
        album = res.get("album") or None

        # Normalize to strings
        title = title or ""
        artist = artist or ""
        album = album or ""
        image = res.get("album_cover") or res.get("spotify") and res.get("spotify").get("album") and res.get("spotify").get("album").get("images") and res.get("spotify").get("album").get("images")[0].get("url")

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
    """Fingerprint audio with `fpcalc` and query AcoustID.

    Returns a dict with keys similar to `match_audio`.
    """
    if not config.acoustid_api_key:
        logging.debug("AcoustID API key not configured")
        return {"status": "no_token"}

    # write clip to temp file
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=".wav")
    tmp.close()
    try:
        _write_clip_to_wav(clip, Path(tmp.name))

        # locate fpcalc: prefer explicit path, otherwise look on PATH
        fpcalc_exe = None
        if config.fpcalc_path:
            fpcalc_exe = config.fpcalc_path
        else:
            fpcalc_exe = shutil.which("fpcalc")

        if not fpcalc_exe:
            logging.error("fpcalc not found; install Chromaprint or set FP_CALC_PATH in .env")
            return {"status": "error", "error": "fpcalc not found; install Chromaprint or set FP_CALC_PATH in .env"}

        # call fpcalc to get fingerprint and duration
        fpcalc_cmd = [fpcalc_exe, str(tmp.name)]
        proc = subprocess.run(fpcalc_cmd, capture_output=True, text=True, timeout=timeout)
        if proc.returncode != 0:
            logging.error("fpcalc failed: %s", proc.stderr.strip())
            raise RuntimeError(f"fpcalc failed: {proc.stderr.strip()}")

        fingerprint = None
        duration = None
        # parse lines like 'FINGERPRINT=...' and 'DURATION=...'
        for line in proc.stdout.splitlines():
            if line.startswith("FINGERPRINT="):
                fingerprint = line.split("=", 1)[1].strip()
            if line.startswith("DURATION="):
                duration = line.split("=", 1)[1].strip()

        if not fingerprint or not duration:
            # try parsing as JSON output (some fpcalc versions support -json)
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

        # pick best result
        best = results[0]
        recordings = []
        title = None
        artist = None
        album = None

        if "recordings" in best and best["recordings"]:
            rec = best["recordings"][0]
            title = rec.get("title")
            if rec.get("artists"):
                artist = ", ".join(a.get("name") for a in rec.get("artists") if a.get("name"))
            # AcoustID doesn't always provide album info; try releasegroups
            if rec.get("releasegroups"):
                album = rec.get("releasegroups")[0].get("title")
        # Normalise return values: ensure strings not None
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
