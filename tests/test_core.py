import os
from pathlib import Path
import unittest
from unittest.mock import MagicMock, patch

import numpy as np

from shazam_project.config import AppConfig
from shazam_project.fft_analyze import analyze_audio
from shazam_project import matcher
from shazam_project.recorder import AudioClip


class CoreTests(unittest.TestCase):
    def test_analyze_audio_creates_file(self):
        sr = 44100
        t = np.linspace(0, 0.2, int(0.2*sr), endpoint=False)
        samples = 0.5 * np.sin(2 * np.pi * 440 * t)
        out = analyze_audio(samples, sr, "tests/test_fft.png")
        self.assertTrue(Path(out).exists())
        # cleanup
        try:
            os.unlink(out)
        except Exception:
            pass

    @patch("shazam_project.matcher.subprocess.run")
    @patch("shazam_project.matcher.requests.get")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    def test_match_audio_acoustid_mock(self, mock_which, mock_get, mock_run):
        # fake fpcalc output
        fake_proc = MagicMock()
        fake_proc.returncode = 0
        fake_proc.stdout = "FINGERPRINT=abc123\nDURATION=1\n"
        fake_proc.stderr = ""
        mock_run.return_value = fake_proc

        # fake acoustid response
        fake_resp = MagicMock()
        fake_resp.status_code = 200
        fake_resp.json.return_value = {
            "results": [
                {
                    "recordings": [
                        {
                            "title": "Test Song",
                            "artists": [{"name": "Tester"}],
                            "releasegroups": [{"title": "Test Album"}],
                        }
                    ]
                }
            ]
        }
        mock_get.return_value = fake_resp

        # create small clip
        sr = 44100
        t = np.linspace(0, 0.1, int(0.1*sr), endpoint=False)
        samples = 0.1 * np.sin(2 * np.pi * 440 * t)
        clip = AudioClip(samples=samples, sample_rate=sr, source="test")

        cfg = AppConfig(audd_api_token="", acoustid_api_key="KEY", fpcalc_path=None)
        result = matcher.match_audio_acoustid(clip, cfg, timeout=5)
        self.assertEqual(result.get("status"), "matched")
        self.assertEqual(result.get("title"), "Test Song")
        artist_val = result.get("artist")
        # allow either a string or list of artist names from different providers
        if isinstance(artist_val, list):
            artist_val = ", ".join(str(x) for x in artist_val)
        # coerce None to empty string for clearer assertion
        artist_val = artist_val or ""
        self.assertIn("Tester", artist_val, msg=f"artist_val did not contain Tester: {artist_val!r}")

    @patch("shazam_project.matcher.match_audio_acoustid")
    @patch("shazam_project.matcher.match_audio_shazam")
    def test_dispatcher_falls_back_after_provider_error(self, mock_shazam, mock_acoustid):
        mock_shazam.return_value = {"status": "error", "error": "temporary outage"}
        mock_acoustid.return_value = {
            "status": "matched",
            "title": "Fallback Song",
            "artist": "Fallback Artist",
        }

        clip = AudioClip(samples=np.zeros(44100, dtype=np.float32), sample_rate=44100, source="test")
        cfg = AppConfig(
            audd_api_token="",
            acoustid_api_key="ACOUSTID",
            fpcalc_path=None,
            rapidapi_key="RAPIDAPI",
        )

        result = matcher.match_audio(clip, cfg)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["backend"], "acoustid")
        self.assertEqual(result["attempts"][0]["status"], "error")
        self.assertEqual(result["attempts"][1]["status"], "matched")

    @patch("shazam_project.matcher._match_audio_audd")
    @patch("shazam_project.matcher.match_audio_shazam")
    def test_dispatcher_falls_back_after_no_match(self, mock_shazam, mock_audd):
        mock_shazam.return_value = {"status": "no_match", "result": None}
        mock_audd.return_value = {
            "status": "matched",
            "title": "AudD Song",
            "artist": "AudD Artist",
        }

        clip = AudioClip(samples=np.zeros(44100, dtype=np.float32), sample_rate=44100, source="test")
        cfg = AppConfig(audd_api_token="AUDD", acoustid_api_key="", rapidapi_key="RAPIDAPI")

        result = matcher.match_audio(clip, cfg)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["backend"], "audd")
        self.assertEqual(
            [item["status"] for item in result["attempts"]],
            ["no_match", "not_configured", "matched"],
        )

    def test_dispatcher_reports_missing_backend(self):
        clip = AudioClip(samples=np.zeros(44100, dtype=np.float32), sample_rate=44100, source="test")
        result = matcher.match_audio(clip, AppConfig(audd_api_token=""))
        self.assertEqual(result["status"], "not_configured")
        self.assertEqual({attempt["status"] for attempt in result["attempts"]}, {"not_configured"})

    @patch("shazam_project.matcher.match_audio_local")
    def test_dispatcher_includes_local_fingerprint_backend(self, mock_local):
        mock_local.return_value = {
            "status": "matched",
            "title": "Local Song",
            "artist": "Local Artist",
        }
        clip = AudioClip(samples=np.zeros(44100, dtype=np.float32), sample_rate=44100, source="test")
        cfg = AppConfig(audd_api_token="", fingerprint_index_path="index.json")

        result = matcher.match_audio(clip, cfg)

        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["backend"], "local")
        mock_local.assert_called_once()


if __name__ == "__main__":
    unittest.main()
