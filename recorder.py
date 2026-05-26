from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
import wave

import numpy as np


@dataclass(frozen=True)
class AudioClip:
	samples: np.ndarray
	sample_rate: int
	source: str
	path: Path | None = None


def _to_mono_float32(samples: np.ndarray) -> np.ndarray:
	array = np.asarray(samples)

	if array.ndim == 1:
		mono = array
	elif array.ndim == 2:
		mono = array.mean(axis=1)
	else:
		raise ValueError("Audio data must be one or two dimensional")

	return np.asarray(mono, dtype=np.float32).reshape(-1)


def _pcm_bytes_to_float32(raw_audio: bytes, sample_width: int) -> np.ndarray:
	if sample_width == 1:
		data = np.frombuffer(raw_audio, dtype=np.uint8).astype(np.float32)
		return (data - 128.0) / 128.0

	if sample_width == 2:
		data = np.frombuffer(raw_audio, dtype=np.int16).astype(np.float32)
		return data / 32768.0

	if sample_width == 4:
		data = np.frombuffer(raw_audio, dtype=np.int32).astype(np.float32)
		return data / 2147483648.0

	raise ValueError(f"Unsupported WAV sample width: {sample_width} bytes")


def load_audio_file(file_path: str | Path) -> AudioClip:
	path = Path(file_path)
	if not path.exists():
		raise FileNotFoundError(f"Audio file not found: {path}")

	if path.suffix.lower() != ".wav":
		raise ValueError("Only WAV files are supported for file mode right now")

	with wave.open(str(path), "rb") as audio_file:
		sample_rate = audio_file.getframerate()
		channels = audio_file.getnchannels()
		sample_width = audio_file.getsampwidth()
		frame_count = audio_file.getnframes()
		raw_audio = audio_file.readframes(frame_count)

	samples = _pcm_bytes_to_float32(raw_audio, sample_width)

	if channels > 1:
		samples = samples.reshape(-1, channels)

	return AudioClip(
		samples=_to_mono_float32(samples),
		sample_rate=sample_rate,
		source="file",
		path=path,
	)


def record_microphone(duration_seconds: int = 8, sample_rate: int = 44100) -> AudioClip:
	try:
		import sounddevice as sd
	except ImportError as exc:  # pragma: no cover - depends on local environment
		raise RuntimeError(
			"Microphone recording requires the 'sounddevice' package"
		) from exc

	if duration_seconds <= 0:
		raise ValueError("duration_seconds must be greater than zero")

	if sample_rate <= 0:
		raise ValueError("sample_rate must be greater than zero")

	frame_count = int(duration_seconds * sample_rate)
	print(f"Recording {duration_seconds} seconds from microphone...")
	audio_data = sd.rec(frame_count, samplerate=sample_rate, channels=1, dtype="float32")
	sd.wait()

	return AudioClip(
		samples=_to_mono_float32(audio_data),
		sample_rate=sample_rate,
		source="microphone",
	)
