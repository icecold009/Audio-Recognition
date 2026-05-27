from __future__ import annotations

import os
import tempfile
from flask import Flask, request, jsonify, render_template
import requests
import shutil
import subprocess

from config import load_config
from recorder import load_audio_file
import matcher

app = Flask(__name__, template_folder="templates", static_folder="static")


@app.route("/")
def index():
    return render_template("index.html")


@app.route("/api/match", methods=["POST"])
def api_match():
    cfg = load_config()


    if "file" not in request.files:
        return jsonify({"status": "error", "error": "No file uploaded"}), 400

    f = request.files["file"]
    # Save uploaded blob to a temp file
    filename = getattr(f, 'filename', None) or 'upload'
    suffix = os.path.splitext(filename)[1] or ''
    tmp = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
    wav_path = None
    try:
        f.save(tmp.name)
        tmp.close()

        # If not WAV, try to convert to WAV using ffmpeg for compatibility
        wav_path = tmp.name
        if not tmp.name.lower().endswith('.wav'):
            ffmpeg_exe = shutil.which('ffmpeg')
            if ffmpeg_exe:
                conv_tmp = tempfile.NamedTemporaryFile(delete=False, suffix='.wav')
                conv_tmp.close()
                try:
                    cmd = [ffmpeg_exe, '-y', '-i', tmp.name, '-ar', '44100', '-ac', '1', conv_tmp.name]
                    subprocess.run(cmd, check=True, capture_output=True)
                    wav_path = conv_tmp.name
                except subprocess.CalledProcessError:
                    # conversion failed; fall back to original file
                    wav_path = tmp.name
            else:
                # ffmpeg not available — proceed with original upload
                wav_path = tmp.name

        # Load the WAV (or original file) as an AudioClip and run the matcher
        try:
            clip = load_audio_file(wav_path)
        except Exception as e:
            # If loading as WAV failed and we are using non-WAV, try to let matcher handle it
            return jsonify({"status": "error", "error": f"Failed to load audio: {e}"}), 400

        # Use the existing matcher which will prefer AcoustID when configured
        result = matcher.match_audio(clip, cfg)

        return jsonify(result)

    except Exception as exc:
        return jsonify({"status": "error", "error": str(exc)}), 500
    finally:
        # clean up any temporary files we created; be defensive about existence
        try:
            if 'tmp' in locals() and getattr(tmp, 'name', None):
                if os.path.exists(tmp.name):
                    try:
                        os.unlink(tmp.name)
                    except Exception:
                        pass
        except Exception:
            pass

        try:
            if wav_path and wav_path != getattr(tmp, 'name', None):
                if os.path.exists(wav_path):
                    try:
                        os.unlink(wav_path)
                    except Exception:
                        pass
        except Exception:
            pass


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

    return jsonify(
        {
            "acoustid_configured": acoustid_configured,
            "audd_configured": audd_configured,
            "fpcalc_on_path": fpcalc_on_path,
            "fpcalc_path_exists": fpcalc_path_exists,
            "ffmpeg_on_path": ffmpeg_on_path,
        }
    )


if __name__ == "__main__":
    app.run(host="127.0.0.1", port=5000, debug=True)
