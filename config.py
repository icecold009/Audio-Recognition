from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os


@dataclass(frozen=True)
class AppConfig:
    audd_api_token: str
    audio_seconds: int = 8
    fft_output_path: Path = Path("fft_output.png")


def _load_env_file(env_path: str | Path) -> None:
    path = Path(env_path)
    if not path.exists():
        return

    for raw_line in path.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue

        key, value = line.split("=", 1)
        key = key.strip()
        value = value.strip().strip('"').strip("'")

        if key and key not in os.environ:
            os.environ[key] = value


def load_config(env_path: str | Path = ".env") -> AppConfig:
    _load_env_file(env_path)
    return AppConfig(
        audd_api_token=os.getenv("AUDD_API_TOKEN", "").strip(),
    )


def missing_configuration(config: AppConfig) -> list[str]:
    missing: list[str] = []
    if not config.audd_api_token:
        missing.append("AUDD_API_TOKEN")
    return missing