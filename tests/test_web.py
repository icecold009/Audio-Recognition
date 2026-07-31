from __future__ import annotations

from io import BytesIO
import unittest
from unittest.mock import patch
import wave

from shazam_project.config import AppConfig
from web import app as web_app


def _wav_bytes(duration_seconds: float = 0.1, sample_rate: int = 8000) -> bytes:
    frame_count = int(duration_seconds * sample_rate)
    payload = b"\x00\x00" * frame_count
    output = BytesIO()
    with wave.open(output, "wb") as wav_file:
        wav_file.setnchannels(1)
        wav_file.setsampwidth(2)
        wav_file.setframerate(sample_rate)
        wav_file.writeframes(payload)
    return output.getvalue()


class WebRouteTests(unittest.TestCase):
    def setUp(self):
        web_app.app.config.update(TESTING=True, MAX_CONTENT_LENGTH=25 * 1024 * 1024)
        web_app.last_request_by_ip.clear()
        web_app.supabase = None
        self.client = web_app.app.test_client()

    def test_status_reports_backend_and_runtime_configuration(self):
        cfg = AppConfig(audd_api_token="", acoustid_api_key="", rapidapi_key="RAPID")
        with patch.object(web_app, "load_config", return_value=cfg), patch.object(
            web_app.shutil, "which", return_value=None
        ):
            response = self.client.get("/api/status")

        self.assertEqual(response.status_code, 200)
        body = response.get_json()
        self.assertTrue(body["rapidapi_configured"])
        self.assertIn("supabase_configured", body)
        self.assertIn("max_audio_seconds", body)

    def test_match_rejects_missing_file(self):
        with patch.object(web_app, "INTERNAL_API_SECRET", ""):
            response = self.client.post("/api/match")
        self.assertEqual(response.status_code, 400)
        self.assertEqual(response.get_json()["status"], "error")

    def test_match_accepts_configured_browser_origin_without_exposing_secret(self):
        cfg = AppConfig(audd_api_token="TOKEN")
        result = {"status": "matched", "title": "Test Song", "artist": "Tester"}
        with patch.object(web_app, "INTERNAL_API_SECRET", "server-only-secret"), patch.object(
            web_app, "load_config", return_value=cfg
        ), patch.object(web_app.matcher, "match_audio", return_value=result) as match_mock:
            response = self.client.post(
                "/api/match",
                data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
                headers={"Origin": "http://localhost:5173"},
            )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.get_json(), result)
        match_mock.assert_called_once()

    def test_match_rejects_unknown_origin_without_secret(self):
        with patch.object(web_app, "INTERNAL_API_SECRET", "server-only-secret"):
            response = self.client.post(
                "/api/match",
                data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
                headers={"Origin": "https://untrusted.example"},
            )

        self.assertEqual(response.status_code, 401)

    def test_match_rejects_audio_over_duration_limit(self):
        cfg = AppConfig(audd_api_token="TOKEN")
        with patch.object(web_app, "MAX_AUDIO_SECONDS", 0), patch.object(
            web_app, "load_config", return_value=cfg
        ), patch.object(web_app.matcher, "match_audio") as match_mock:
            response = self.client.post(
                "/api/match",
                data={"file": (BytesIO(_wav_bytes()), "sample.wav")},
                headers={"Origin": "http://localhost:5173"},
            )

        self.assertEqual(response.status_code, 413)
        match_mock.assert_not_called()


if __name__ == "__main__":
    unittest.main()
