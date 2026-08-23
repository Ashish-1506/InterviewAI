from __future__ import annotations

import asyncio
import os
import tempfile
import threading
from dataclasses import dataclass
from typing import Any, Optional

from app.core.config import Settings


@dataclass
class STTResult:
    text: str
    audio_duration_ms: int = 0


class STTProvider:
    def __init__(self, settings: Settings):
        self.settings = settings

    async def warmup(self) -> None:
        """Optional hook for expensive model preloading."""
        return None

    async def transcribe_bytes(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> STTResult:
        raise NotImplementedError


class WhisperSTTProvider(STTProvider):
    """Uses openai-whisper for transcription.

    Note: for production, consider faster-whisper.
    """

    _shared_model: Any = None
    _model_load_attempted = False
    _model_lock = threading.Lock()

    def __init__(self, settings: Settings):
        super().__init__(settings)
        self._model = None

    def _load_model_once(self) -> Any:
        """Load Whisper only when audio is actually submitted.

        Loading can download hundreds of megabytes and must never delay the
        first interview question or WebSocket handshake.
        """
        cls = type(self)
        with cls._model_lock:
            if cls._model_load_attempted:
                return cls._shared_model

            cls._model_load_attempted = True
            try:
                import whisper

                cls._shared_model = whisper.load_model(self.settings.stt_whisper_model or "base")
            except Exception:
                cls._shared_model = None
            return cls._shared_model

    async def warmup(self) -> None:
        await self._ensure_model()

    async def _ensure_model(self) -> Any:
        if self._model is None:
            self._model = await asyncio.to_thread(self._load_model_once)
        return self._model

    def _write_temp_audio_file(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> str:
        suffix = ".webm"
        if mime_type:
            if "mpeg" in mime_type or "mp3" in mime_type:
                suffix = ".mp3"
            elif "wav" in mime_type:
                suffix = ".wav"
            elif "ogg" in mime_type:
                suffix = ".ogg"

        handle = tempfile.NamedTemporaryFile(delete=False, suffix=suffix)
        try:
            handle.write(audio_bytes)
            handle.flush()
            return handle.name
        finally:
            handle.close()

    def _estimate_duration_ms(self, file_path: str) -> int:
        try:
            from pydub import AudioSegment

            return int(len(AudioSegment.from_file(file_path)))
        except Exception:
            return 0

    async def transcribe_bytes(self, audio_bytes: bytes, mime_type: Optional[str] = None) -> STTResult:
        model = await self._ensure_model()
        if model is None:
            return STTResult(text="", audio_duration_ms=0)

        temp_path = self._write_temp_audio_file(audio_bytes, mime_type=mime_type)

        try:
            result: dict[str, Any] = await asyncio.to_thread(model.transcribe, temp_path)
            text = (result.get("text") or "").strip()
            duration_ms = self._estimate_duration_ms(temp_path)
            return STTResult(text=text, audio_duration_ms=duration_ms)
        finally:
            try:
                os.unlink(temp_path)
            except Exception:
                pass


def build_stt_provider(settings: Settings) -> STTProvider:
    provider = (settings.stt_provider or "whisper").lower()

    if provider == "whisper":
        return WhisperSTTProvider(settings)

    raise ValueError(f"Unsupported stt_provider: {provider}")

