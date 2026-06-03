from __future__ import annotations

from dataclasses import dataclass
import os
from pathlib import Path

from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    audd_api_token: str
    acoustid_api_key: str = ""
    fpcalc_path: str | None = None
    audio_seconds: int = 8
    fft_output_path: Path = Path("fft_output.png")
    rapidapi_key: str = ""


def load_config(env_path: str | Path = ".env") -> AppConfig:
    path = Path(env_path)
    if path.exists():
        load_dotenv(dotenv_path=str(path))

    return AppConfig(
        audd_api_token=os.getenv("AUDD_API_TOKEN", "").strip(),
        acoustid_api_key=os.getenv("ACOUSTID_API_KEY", "").strip(),
        fpcalc_path=os.getenv("FP_CALC_PATH", None),
        rapidapi_key=os.getenv("RAPIDAPI_KEY", "").strip(),
    )


def missing_configuration(config: AppConfig) -> list[str]:
    missing: list[str] = []
    if not (config.audd_api_token or config.acoustid_api_key or config.rapidapi_key):
        missing.append("AUDD_API_TOKEN or ACOUSTID_API_KEY or RAPIDAPI_KEY")

    if config.acoustid_api_key and config.fpcalc_path:
        try:
            p = Path(config.fpcalc_path)
            if not p.exists():
                missing.append("FP_CALC_PATH (path does not exist)")
        except Exception:
            missing.append("FP_CALC_PATH (invalid)")
    return missing