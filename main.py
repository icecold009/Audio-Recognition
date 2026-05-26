from __future__ import annotations

import sys

from config import load_config, missing_configuration


def main() -> int:
    print("DIY Shazam - startup check")

    config = load_config()
    missing = missing_configuration(config)

    if missing:
        print("Missing required configuration:")
        for name in missing:
            print(f"- {name}")
        print()
        print("Create a .env file in the repo root and add:")
        print("AUDD_API_TOKEN=your_token_here")
        print("\nThe application will stop here until the token is configured.")
        return 1

    print("Configuration loaded successfully.")
    print("Phase 1 foundation is ready: environment loading and startup validation are in place.")
    print("Next steps are audio input, FFT analysis, and AudD matching.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())