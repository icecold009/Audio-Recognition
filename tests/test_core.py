import unittest
import os
from pathlib import Path
from unittest.mock import patch, MagicMock

import numpy as np

from fft_analyze import analyze_audio
from recorder import AudioClip
import matcher
from config import AppConfig


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

    @patch("matcher.subprocess.run")
    @patch("matcher.requests.get")
    @patch("matcher.shutil.which", return_value="fpcalc")
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


if __name__ == "__main__":
    unittest.main()
