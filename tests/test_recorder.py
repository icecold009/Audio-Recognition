from __future__ import annotations

import sys
from unittest.mock import MagicMock, patch

import numpy as np
import pytest

from shazam_project.config import AppConfig
from shazam_project.recorder import AudioInputError, record_microphone


def _config() -> AppConfig:
    return AppConfig(
        audd_api_token="",
        internal_sample_rate=16000,
        min_audio_seconds=1.0,
        max_audio_seconds=2.0,
    )


@pytest.mark.parametrize(
    ("duration", "code"),
    [(0, "invalid_duration"), (-1, "invalid_duration"), (0.5, "too_short"), (3, "too_long")],
)
def test_invalid_duration_is_rejected_before_capture(duration, code):
    sounddevice = MagicMock()
    with patch.dict(sys.modules, {"sounddevice": sounddevice}):
        with pytest.raises(AudioInputError) as error:
            record_microphone(duration, sample_rate=16000, config=_config())

    assert error.value.code == code
    sounddevice.rec.assert_not_called()


@pytest.mark.parametrize("sample_rate", [0, -16000, "not-a-rate"])
def test_invalid_sample_rate_is_rejected_before_capture(sample_rate):
    sounddevice = MagicMock()
    with patch.dict(sys.modules, {"sounddevice": sounddevice}):
        with pytest.raises(AudioInputError) as error:
            record_microphone(1, sample_rate=sample_rate, config=_config())

    assert error.value.code == "invalid_sample_rate"
    sounddevice.rec.assert_not_called()


def test_missing_sounddevice_dependency_is_explicit():
    with patch.dict(sys.modules, {"sounddevice": None}):
        with pytest.raises(RuntimeError, match="sounddevice"):
            record_microphone(1, sample_rate=16000, config=_config())


def test_capture_failure_is_safe_and_stops_device(caplog):
    sounddevice = MagicMock()
    sounddevice.rec.return_value = np.zeros((16000, 1), dtype=np.float32)
    sounddevice.wait.side_effect = RuntimeError("device secret capture details")

    with patch.dict(sys.modules, {"sounddevice": sounddevice}), caplog.at_level("ERROR"):
        with pytest.raises(AudioInputError) as error:
            record_microphone(1, sample_rate=16000, config=_config())

    assert error.value.code == "recording_failed"
    sounddevice.stop.assert_called_once_with()
    assert "device secret" not in caplog.text


def test_device_failure_is_safe_and_stops_device(caplog):
    sounddevice = MagicMock()
    sounddevice.rec.side_effect = RuntimeError("private device path")

    with patch.dict(sys.modules, {"sounddevice": sounddevice}), caplog.at_level("ERROR"):
        with pytest.raises(AudioInputError) as error:
            record_microphone(1, sample_rate=16000, config=_config())

    assert error.value.code == "recording_failed"
    sounddevice.stop.assert_called_once_with()
    assert "private device path" not in caplog.text


def test_successful_capture_releases_device_resources():
    sounddevice = MagicMock()
    sounddevice.rec.return_value = np.zeros((16000, 1), dtype=np.float32)

    with patch.dict(sys.modules, {"sounddevice": sounddevice}):
        clip = record_microphone(1, sample_rate=16000, config=_config())

    assert clip.sample_rate == 16000
    assert clip.samples.dtype == np.float32
    sounddevice.wait.assert_called_once_with()
    sounddevice.stop.assert_called_once_with()


def test_invalid_capture_data_still_releases_device_resources():
    sounddevice = MagicMock()
    sounddevice.rec.return_value = np.zeros((0, 1), dtype=np.float32)

    with patch.dict(sys.modules, {"sounddevice": sounddevice}):
        with pytest.raises(AudioInputError) as error:
            record_microphone(1, sample_rate=16000, config=_config())

    assert error.value.code == "empty_audio"
    sounddevice.stop.assert_called_once_with()


def test_cleanup_failure_does_not_replace_successful_capture(caplog):
    sounddevice = MagicMock()
    sounddevice.rec.return_value = np.zeros((16000, 1), dtype=np.float32)
    sounddevice.stop.side_effect = RuntimeError("cleanup detail")

    with patch.dict(sys.modules, {"sounddevice": sounddevice}), caplog.at_level("ERROR"):
        clip = record_microphone(1, sample_rate=16000, config=_config())

    assert clip.sample_rate == 16000
    assert "cleanup detail" not in caplog.text
