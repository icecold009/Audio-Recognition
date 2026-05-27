from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import os
from dotenv import load_dotenv


@dataclass(frozen=True)
class AppConfig:
    audd_api_token: str
    acoustid_api_key: str = ""
    fpcalc_path: str | None = None
    audio_seconds: int = 8
    fft_output_path: Path = Path("fft_output.png")


def load_config(env_path: str | Path = ".env") -> AppConfig:
    # Use python-dotenv to load environment file if present
    path = Path(env_path)
    if path.exists():
        load_dotenv(dotenv_path=str(path))

    return AppConfig(
        audd_api_token=os.getenv("AUDD_API_TOKEN", "").strip(),
        acoustid_api_key=os.getenv("ACOUSTID_API_KEY", "").strip(),
        fpcalc_path=os.getenv("FP_CALC_PATH", None),
    )


def missing_configuration(config: AppConfig) -> list[str]:
    missing: list[str] = []
    # Require at least one matching provider: AudD or AcoustID
    if not (config.audd_api_token or config.acoustid_api_key):
        missing.append("AUDD_API_TOKEN or ACOUSTID_API_KEY")

    # If AcoustID is configured with an explicit fpcalc path, ensure it exists
    if config.acoustid_api_key and config.fpcalc_path:
        try:
            from pathlib import Path

            p = Path(config.fpcalc_path)
            if not p.exists():
                missing.append("FP_CALC_PATH (path does not exist)")
        except Exception:
            missing.append("FP_CALC_PATH (invalid)")
    return missing