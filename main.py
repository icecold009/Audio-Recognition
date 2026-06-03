from __future__ import annotations

from shazam_project.config import load_config, missing_configuration
from shazam_project.display import show_result
from shazam_project.fft_analyze import analyze_audio
from shazam_project.matcher import match_audio
from shazam_project.recorder import load_audio_file, record_microphone


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
            duration_seconds = int(duration) if duration else config.audio_seconds
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

    try:
        fft_output = analyze_audio(clip.samples, clip.sample_rate, config.fft_output_path)
    except ValueError as exc:
        print(f"FFT analysis error: {exc}")
        return 1

    print(f"FFT analysis saved to {fft_output}")
    print("Audio input and FFT analysis are ready for the next phase: matching.")

    try:
        result = match_audio(clip, config)
    except Exception as exc:
        print(f"Matching error: {exc}")
        return 1

    show_result(result)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())