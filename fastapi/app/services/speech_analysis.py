from __future__ import annotations

import re
from dataclasses import dataclass

from app.schemas.interview_voice import SpeechStatsOut


FILLER_WORDS = ["um", "uh", "like", "you know"]


def _tokenize_words(text: str) -> list[str]:
    # keep apostrophes inside words
    return re.findall(r"[a-zA-Z']+", text.lower())


def _count_filler(text: str) -> int:
    t = text.lower()
    count = 0
    for w in FILLER_WORDS:
        if w in {"you know"}:
            # phrase match
            count += len(re.findall(r"\byou\s+know\b", t))
        else:
            count += len(re.findall(rf"\b{re.escape(w)}\b", t))
    return count


def _estimate_wpm(text: str, audio_duration_ms: int) -> float:
    if not text.strip() or audio_duration_ms <= 0:
        # Fallback: assume 15s per answer for baseline
        assumed_s = 15.0
    else:
        assumed_s = audio_duration_ms / 1000.0

    words = max(len(_tokenize_words(text)), 1)
    minutes = assumed_s / 60.0
    return (words / minutes) if minutes > 0 else float(words)


def _avg_pause_length_between_sentences(text: str, audio_duration_ms: int) -> float:
    # Heuristic: split sentences and assume evenly distributed pauses.
    # If no punctuation, return 0.
    sentences = re.split(r"[.!?]+", text.strip())
    sentences = [s.strip() for s in sentences if s.strip()]
    if len(sentences) <= 1:
        return 0.0

    if audio_duration_ms <= 0:
        # unknown duration; use 0.8s default pause proxy
        total_pause_s = (len(sentences) - 1) * 0.8
    else:
        # total time minus approximate speaking time estimate
        # speaking time approx: words / (wpm-derived); we don't have wpm here, use rough 130 wpm.
        words = len(_tokenize_words(text))
        speaking_minutes = words / 130.0
        speaking_s = speaking_minutes * 60.0
        total_pause_s = max((audio_duration_ms / 1000.0) - speaking_s, 0.0)

    pauses = max(len(sentences) - 1, 1)
    return total_pause_s / pauses


def compute_speech_stats(transcript: str, audio_duration_ms: int) -> SpeechStatsOut:
    transcript = transcript or ""
    filler_word_count = _count_filler(transcript)
    wpm = _estimate_wpm(transcript, audio_duration_ms)
    avg_pause_length_s = _avg_pause_length_between_sentences(transcript, audio_duration_ms)

    # Confidence proxy: penalize filler rate and extreme pauses; reward moderate pace.
    # Normalize filler count by estimated minutes.
    minutes = (audio_duration_ms / 1000.0) / 60.0 if audio_duration_ms > 0 else 0.25
    filler_rate = filler_word_count / minutes if minutes > 0 else filler_word_count

    # Score components
    pace_score = max(0.0, 1.0 - abs(wpm - 150.0) / 150.0)  # peak near 150 wpm
    filler_score = max(0.0, 1.0 - filler_rate / 20.0)
    pause_score = max(0.0, 1.0 - abs(avg_pause_length_s - 1.0) / 3.0)

    verbal_conf = int(round(100.0 * (0.45 * pace_score + 0.35 * filler_score + 0.20 * pause_score)))
    verbal_conf = max(0, min(100, verbal_conf))

    return SpeechStatsOut(
        filler_word_count=filler_word_count,
        wpm=wpm,
        avg_pause_length_s=avg_pause_length_s,
        verbal_confidence=verbal_conf,
    )

