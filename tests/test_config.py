from __future__ import annotations

import os

import pytest

from shazam_project.config import AppConfig, load_config, missing_configuration

CONFIG_KEYS = (
    "AUDD_API_TOKEN",
    "ACOUSTID_API_KEY",
    "FP_CALC_PATH",
    "RAPIDAPI_KEY",
    "INTERNAL_SAMPLE_RATE",
    "MIN_AUDIO_SECONDS",
    "MAX_AUDIO_SECONDS",
    "MAX_UPLOAD_BYTES",
    "FFMPEG_TIMEOUT_SECONDS",
    "LOCAL_FINGERPRINT_INDEX",
    "FINGERPRINT_INDEX_PATH",
    "PYTHON_DOTENV_DISABLED",
)


@pytest.fixture
def clean_config_environment():
    original = {key: os.environ.get(key) for key in CONFIG_KEYS}
    for key in CONFIG_KEYS:
        os.environ.pop(key, None)
    yield
    for key, value in original.items():
        if value is None:
            os.environ.pop(key, None)
        else:
            os.environ[key] = value


def test_load_config_reads_dotenv_values(tmp_path, clean_config_environment):
    env_file = tmp_path / ".env.test"
    env_file.write_text(
        "RAPIDAPI_KEY=rapid-from-file\n"
        "INTERNAL_SAMPLE_RATE=22050\n"
        "MIN_AUDIO_SECONDS=1.5\n"
        "MAX_UPLOAD_BYTES=12345\n",
        encoding="utf-8",
    )

    config = load_config(env_file)

    assert config.rapidapi_key == "rapid-from-file"
    assert config.internal_sample_rate == 22050
    assert config.min_audio_seconds == 1.5
    assert config.max_upload_bytes == 12345


def test_process_environment_takes_precedence_over_dotenv(tmp_path, clean_config_environment):
    env_file = tmp_path / ".env.test"
    env_file.write_text("RAPIDAPI_KEY=file-value\n", encoding="utf-8")
    os.environ["RAPIDAPI_KEY"] = "process-value"

    config = load_config(env_file)

    assert config.rapidapi_key == "process-value"


def test_invalid_numeric_environment_values_use_safe_defaults(clean_config_environment, tmp_path):
    os.environ.update(
        {
            "INTERNAL_SAMPLE_RATE": "not-an-int",
            "MIN_AUDIO_SECONDS": "not-a-float",
            "MAX_UPLOAD_BYTES": "also-not-an-int",
        }
    )

    config = load_config(tmp_path / "missing.env")

    assert config.internal_sample_rate == 44100
    assert config.min_audio_seconds == 1.0
    assert config.max_upload_bytes == 10 * 1024 * 1024


def test_missing_configuration_reports_no_backend():
    missing = missing_configuration(AppConfig(audd_api_token=""))

    assert missing == [
        "AUDD_API_TOKEN or ACOUSTID_API_KEY or RAPIDAPI_KEY or LOCAL_FINGERPRINT_INDEX"
    ]


@pytest.mark.parametrize(
    "kwargs",
    [
        {"audd_api_token": "audd"},
        {"acoustid_api_key": "acoustid"},
        {"rapidapi_key": "rapid"},
    ],
)
def test_each_provider_backend_satisfies_configuration(kwargs):
    values = {"audd_api_token": ""}
    values.update(kwargs)
    assert missing_configuration(AppConfig(**values)) == []


def test_existing_local_index_satisfies_configuration(tmp_path):
    index = tmp_path / "fingerprints.json"
    index.write_text("{}", encoding="utf-8")

    config = AppConfig(audd_api_token="", fingerprint_index_path=str(index))

    assert missing_configuration(config) == []


def test_invalid_fpcalc_path_is_reported_when_acoustid_is_enabled(tmp_path):
    config = AppConfig(
        audd_api_token="",
        acoustid_api_key="acoustid",
        fpcalc_path=str(tmp_path / "missing-fpcalc"),
    )

    assert "FP_CALC_PATH (path does not exist)" in missing_configuration(config)


def test_invalid_fpcalc_value_is_reported_without_echoing_the_value():
    config = AppConfig(audd_api_token="", acoustid_api_key="acoustid", fpcalc_path=object())

    missing = missing_configuration(config)

    assert missing == ["FP_CALC_PATH (invalid)"]


def test_missing_local_fingerprint_index_is_reported(tmp_path):
    config = AppConfig(
        audd_api_token="",
        fingerprint_index_path=str(tmp_path / "missing-index.json"),
    )

    assert "LOCAL_FINGERPRINT_INDEX (path does not exist)" in missing_configuration(config)


def test_invalid_local_index_value_is_reported_without_echoing_the_value():
    config = AppConfig(audd_api_token="", fingerprint_index_path=object())

    assert missing_configuration(config) == ["LOCAL_FINGERPRINT_INDEX (invalid)"]
