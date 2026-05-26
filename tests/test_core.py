from __future__ import annotations

import io
import math
import struct
import tempfile
import wave
from contextlib import redirect_stdout
from pathlib import Path
from types import SimpleNamespace
from unittest import TestCase

import numpy as np

from config import AppConfig, missing_configuration
from display import show_result
from fft_analyze import analyze_audio
from matcher import match_audio
from recorder import load_audio_file


class CoreTests(TestCase):
    def _write_wav(self, path: Path, sample_rate: int = 8000) -> None:
        frames = bytearray()
        for index in range(sample_rate // 10):
            sample = int(32767 * 0.5 * math.sin(2 * math.pi * 440 * index / sample_rate))
            frames += struct.pack("<hh", sample, sample)

        with wave.open(str(path), "wb") as wav_file:
            wav_file.setnchannels(2)
            wav_file.setsampwidth(2)
            wav_file.setframerate(sample_rate)
            wav_file.writeframes(frames)

    def test_load_audio_file_converts_stereo_wav_to_mono(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            wav_path = Path(tmpdir) / "sample.wav"
            self._write_wav(wav_path)

            clip = load_audio_file(wav_path)

            self.assertEqual(clip.source, "file")
            self.assertEqual(clip.sample_rate, 8000)
            self.assertEqual(clip.path, wav_path)
            self.assertEqual(clip.samples.ndim, 1)
            self.assertGreater(clip.samples.size, 0)

    def test_analyze_audio_writes_fft_image(self) -> None:
        with tempfile.TemporaryDirectory() as tmpdir:
            output_path = Path(tmpdir) / "fft.png"
            samples = np.sin(np.linspace(0, 2 * np.pi, 256, endpoint=False)).astype(np.float32)

            result_path = analyze_audio(samples, 8000, output_path)

            self.assertEqual(result_path, output_path)
            self.assertTrue(output_path.exists())

    def test_missing_configuration_requires_audd_or_acoustid(self) -> None:
        config = AppConfig(audd_api_token="", acoustid_api_key="", fpcalc_path=None)

        self.assertEqual(missing_configuration(config), ["AUDD_API_TOKEN or ACOUSTID_API_KEY"])

    def test_missing_configuration_validates_fpcalc_path(self) -> None:
        config = AppConfig(audd_api_token="", acoustid_api_key="key", fpcalc_path="/does/not/exist")

        self.assertEqual(missing_configuration(config), ["FP_CALC_PATH (path does not exist)"])

    def test_match_audio_without_token_reports_disabled_recognition(self) -> None:
        clip = SimpleNamespace(samples=np.zeros(32, dtype=np.float32), sample_rate=8000)
        result = match_audio(clip, AppConfig(audd_api_token=""))

        self.assertEqual(result["status"], "no_token")

    def test_show_result_prints_no_token_message(self) -> None:
        buffer = io.StringIO()
        with redirect_stdout(buffer):
            show_result({"status": "no_token"})

        self.assertIn("Recognition disabled", buffer.getvalue())
