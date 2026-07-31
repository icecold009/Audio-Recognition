import subprocess
import unittest
from pathlib import Path
from unittest.mock import MagicMock, patch

import numpy as np
import requests

from shazam_project import matcher
from shazam_project.config import AppConfig
from shazam_project.recorder import AudioClip


def _clip() -> AudioClip:
    return AudioClip(
        samples=np.zeros(4410, dtype=np.float32),
        sample_rate=44100,
        source="provider-test",
    )


def _response(status_code: int = 200, body=None, json_error: Exception | None = None):
    response = MagicMock()
    response.status_code = status_code
    if json_error is not None:
        response.json.side_effect = json_error
    else:
        response.json.return_value = body or {}
    return response


class ProviderAdapterTests(unittest.TestCase):
    def _assert_error(self, result, code: str, detail: str):
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error_code"], code)
        self.assertIn(detail, result["error"])

    def _assert_temp_file_removed(self, write_mock):
        temp_path = Path(write_mock.call_args.args[1])
        self.assertFalse(temp_path.exists(), f"temporary file remained: {temp_path}")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.requests.post")
    def test_rapidapi_success_removes_temp_file(self, post, write):
        post.return_value = _response(
            body={
                "track": {
                    "title": "Rapid Song",
                    "subtitle": "Rapid Artist",
                    "images": {"coverart": "cover.jpg"},
                }
            }
        )
        result = matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["title"], "Rapid Song")
        self.assertEqual(result["artist"], "Rapid Artist")
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.requests.post")
    def test_rapidapi_no_match(self, post):
        post.return_value = _response(body={})
        result = matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self.assertEqual(result, {"status": "no_match", "result": None})

    @patch("shazam_project.matcher.requests.post")
    def test_rapidapi_http_error(self, post):
        post.return_value = _response(status_code=503)
        result = matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self._assert_error(result, "http_error", "RapidAPI HTTP 503")

    @patch("shazam_project.matcher.requests.post", side_effect=requests.Timeout("slow"))
    def test_rapidapi_timeout(self, post):
        result = matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self._assert_error(result, "timeout", "RapidAPI request timed out")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.requests.post", side_effect=requests.Timeout("slow"))
    def test_rapidapi_timeout_removes_temp_file(self, post, write):
        matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.requests.post")
    def test_rapidapi_malformed_json(self, post):
        post.return_value = _response(json_error=ValueError("not json"))
        result = matcher.match_audio_shazam(_clip(), AppConfig("", rapidapi_key="KEY"))
        self._assert_error(result, "malformed_response", "RapidAPI returned invalid JSON")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.requests.post")
    def test_audd_success_removes_temp_file(self, post, write):
        post.return_value = _response(
            body={
                "result": {
                    "title": "AudD Song",
                    "artist": "AudD Artist",
                    "album": "AudD Album",
                }
            }
        )
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["title"], "AudD Song")
        self.assertEqual(result["album"], "AudD Album")
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.requests.post")
    def test_audd_no_match(self, post):
        post.return_value = _response(body={"result": None})
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self.assertEqual(result, {"status": "no_match", "result": None})

    @patch("shazam_project.matcher.requests.post")
    def test_audd_http_error(self, post):
        post.return_value = _response(status_code=429)
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self._assert_error(result, "http_error", "AudD HTTP 429")

    @patch("shazam_project.matcher.requests.post", side_effect=requests.Timeout("slow"))
    def test_audd_timeout(self, post):
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self._assert_error(result, "timeout", "AudD request timed out")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.requests.post", side_effect=RuntimeError("unexpected"))
    def test_audd_provider_exception_removes_temp_file(self, post, write):
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self._assert_error(result, "provider_error", "AudD provider error")
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.requests.post")
    def test_audd_malformed_json(self, post):
        post.return_value = _response(json_error=ValueError("not json"))
        result = matcher._match_audio_audd(_clip(), AppConfig("TOKEN"))
        self._assert_error(result, "malformed_response", "AudD returned invalid JSON")

    def _fpcalc_success(self):
        return MagicMock(returncode=0, stdout="FINGERPRINT=abc\nDURATION=8\n", stderr="")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.requests.get")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_success_removes_temp_file(self, run, which, get, write):
        run.return_value = self._fpcalc_success()
        get.return_value = _response(
            body={
                "results": [
                    {
                        "recordings": [
                            {
                                "title": "AcoustID Song",
                                "artists": [{"name": "AcoustID Artist"}],
                                "releasegroups": [{"title": "AcoustID Album"}],
                            }
                        ]
                    }
                ]
            }
        )
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self.assertEqual(result["status"], "matched")
        self.assertEqual(result["title"], "AcoustID Song")
        self.assertEqual(result["artist"], "AcoustID Artist")
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.shutil.which", return_value=None)
    def test_acoustid_missing_fpcalc(self, which):
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "configuration_error", "fpcalc not found")

    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_fpcalc_failure(self, run, which):
        run.return_value = MagicMock(returncode=1, stdout="", stderr="bad audio")
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "fpcalc_error", "fpcalc failed")

    @patch("shazam_project.matcher._write_clip_to_wav")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run", side_effect=subprocess.TimeoutExpired("fpcalc", 1))
    def test_acoustid_timeout_removes_temp_file(self, run, which, write):
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "timeout", "AcoustID fingerprinting timed out")
        self._assert_temp_file_removed(write)

    @patch("shazam_project.matcher.requests.get")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_no_match(self, run, which, get):
        run.return_value = self._fpcalc_success()
        get.return_value = _response(body={"results": []})
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self.assertEqual(result, {"status": "no_match", "result": None})

    @patch("shazam_project.matcher.requests.get")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_http_error(self, run, which, get):
        run.return_value = self._fpcalc_success()
        get.return_value = _response(status_code=500)
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "http_error", "AcoustID HTTP 500")

    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_malformed_fpcalc_output(self, run, which):
        run.return_value = MagicMock(returncode=0, stdout="not a fingerprint", stderr="")
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "fpcalc_output_error", "Could not obtain fingerprint")

    @patch("shazam_project.matcher.requests.get")
    @patch("shazam_project.matcher.shutil.which", return_value="fpcalc")
    @patch("shazam_project.matcher.subprocess.run")
    def test_acoustid_malformed_json(self, run, which, get):
        run.return_value = self._fpcalc_success()
        get.return_value = _response(json_error=ValueError("not json"))
        result = matcher.match_audio_acoustid(_clip(), AppConfig("", acoustid_api_key="KEY"))
        self._assert_error(result, "malformed_response", "AcoustID returned invalid JSON")


if __name__ == "__main__":
    unittest.main()
