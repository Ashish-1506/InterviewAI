import sys
import types

import pytest

from app.core.config import Settings
from app.services.stt_provider import WhisperSTTProvider


@pytest.mark.asyncio
async def test_whisper_warmup_loads_model_once(monkeypatch):
    calls = {"count": 0}

    class FakeModel:
        def transcribe(self, path):
            return {"text": "hello world"}

    fake_whisper = types.SimpleNamespace(
        load_model=lambda model_name: (calls.__setitem__("count", calls["count"] + 1) or FakeModel())
    )

    monkeypatch.setitem(sys.modules, "whisper", fake_whisper)

    provider = WhisperSTTProvider(Settings())
    await provider.warmup()
    await provider.warmup()

    assert provider._model is not None
    assert calls["count"] == 1
