from __future__ import annotations

import sys

from config import load_config, missing_configuration
from recorder import load_audio_file, record_microphone


def main() -> int:
    print("DIY Shazam - startup check")

    config = load_config()
    missing = missing_configuration(config)

    if missing:
        print("Missing required configuration:")
        for name in missing:
            print(f"- {name}")
        print()
        print("The app can still record and load audio now.")
        print("Recognition will stay disabled until the token is added later.")

    print("Configuration loaded successfully.")

    mode = input("Listen via microphone or load a file? (mic/file): ").strip().lower()

    try:
        if mode == "mic":
            duration = input("Recording length in seconds [8]: ").strip()
            duration_seconds = int(duration) if duration else 8
            clip = record_microphone(duration_seconds=duration_seconds)
            print(f"Captured {len(clip.samples)} samples at {clip.sample_rate} Hz from microphone.")
        elif mode == "file":
            file_path = input("Enter a WAV file path: ").strip().strip('"')
            clip = load_audio_file(file_path)
            print(f"Loaded {clip.path} with {len(clip.samples)} samples at {clip.sample_rate} Hz.")
        else:
            print("Invalid choice. Use 'mic' or 'file'.")
            return 1
    except (ValueError, FileNotFoundError, RuntimeError) as exc:
        print(f"Audio input error: {exc}")
        return 1

    print("Audio input is ready for the next phase: FFT analysis.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())