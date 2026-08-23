from __future__ import annotations

import asyncio
import base64
import io
import wave
from dataclasses import dataclass

import numpy as np

from app.core.config import Settings


@dataclass
class TTSResult:
    audio_b64: str
    mime_type: str


@dataclass
class TTSProvider:
    settings: Settings

    async def synthesize_speech(self, text: str, mime_type: str = "audio/wav") -> TTSResult | None:
        raise NotImplementedError


@dataclass
class NoOpTTSProvider(TTSProvider):
    """Deliberately omit server-generated audio.

    The web client uses the browser's built-in speech synthesis in this mode.
    This keeps a new interview responsive instead of downloading and loading a
    large neural TTS model during the first WebSocket request.
    """

    async def synthesize_speech(self, text: str, mime_type: str = "audio/wav") -> TTSResult | None:
        return None


@dataclass
class CoquiTTSProvider(TTSProvider):
    def __post_init__(self) -> None:
        from TTS.api import TTS

        self._tts = TTS(
            model_name=self.settings.coqui_model,
            progress_bar=False,
        )
        if self.settings.coqui_gpu:
            self._tts = self._tts.to("cuda")

    def _synthesize_wav(self, text: str) -> bytes:
        samples = np.asarray(self._tts.tts(text=text), dtype=np.float32)
        samples = np.clip(samples, -1.0, 1.0)
        pcm = (samples * 32767.0).astype(np.int16).tobytes()
        sample_rate = int(getattr(self._tts.synthesizer, "output_sample_rate", 22050))

        buffer = io.BytesIO()
        with wave.open(buffer, "wb") as output:
            output.setnchannels(1)
            output.setsampwidth(2)
            output.setframerate(sample_rate)
            output.writeframes(pcm)
        return buffer.getvalue()

    async def synthesize_speech(self, text: str, mime_type: str = "audio/wav") -> TTSResult:
        audio_bytes = await asyncio.to_thread(self._synthesize_wav, text)
        audio_b64 = base64.b64encode(audio_bytes).decode("ascii")
        return TTSResult(audio_b64=audio_b64, mime_type="audio/wav")


def build_tts_provider(settings: Settings) -> TTSProvider:
    provider = (settings.tts_provider or "none").lower()

    if provider in {"none", "browser", "disabled"}:
        return NoOpTTSProvider(settings=settings)

    if provider in {"coqui", "coqui_tts"}:
        return CoquiTTSProvider(settings=settings)

    raise ValueError(f"Unsupported tts_provider: {provider}")

