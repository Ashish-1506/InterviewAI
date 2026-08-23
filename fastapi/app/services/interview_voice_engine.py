from __future__ import annotations

import base64
from dataclasses import dataclass
from datetime import datetime
from typing import Any, Optional

from app.core.config import Settings
from app.services.interviewer_engine import InterviewerEngine
from app.services.mongo_store import MongoStore
from app.services.stt_provider import build_stt_provider
from app.services.tts_provider import build_tts_provider
from app.services.speech_analysis import compute_speech_stats
from app.schemas.interview_turn import InterviewTurnOut
from app.schemas.interview_voice import InterviewTurnOutVoice, VoiceTranscriptOut


@dataclass
class InterviewVoiceEngine:
    settings: Settings
    mongo: MongoStore
    interviewer: InterviewerEngine

    def __post_init__(self) -> None:
        self._stt = build_stt_provider(self.settings)
        self._tts = build_tts_provider(self.settings)

    async def transcribe_audio_b64(self, audio_b64: str) -> VoiceTranscriptOut:
        audio_bytes = base64.b64decode(audio_b64)
        return await self.transcribe_audio_bytes(audio_bytes=audio_bytes, mime_type=None)

    async def transcribe_audio_bytes(
        self,
        audio_bytes: bytes,
        mime_type: str | None = None,
    ) -> VoiceTranscriptOut:
        # mime_type is currently unused by STT providers but kept for swappability.
        stt_res = await self._stt.transcribe_bytes(audio_bytes, mime_type=mime_type)
        return VoiceTranscriptOut(transcript=stt_res.text, audio_duration_ms=stt_res.audio_duration_ms)


    async def handle_candidate_transcript(
        self,
        session_doc: dict[str, Any],
        session_id: str,
        transcript: str,
        audio_duration_ms: int,
    ) -> InterviewTurnOutVoice:
        # Update InterviewSession conversation turns using the interviewer engine
        turns_before = session_doc.get("conversationTurns") or []
        answered_turn_index = len(turns_before) - 1

        interview_type = session_doc.get("type") or "HR"

        next_out = await self.interviewer.process_candidate_answer(
            session_id=session_id,
            answer=transcript,
            received_at=datetime.utcnow(),
        )

        await self.mongo.append_conversation_turn(
            session_id=session_id,
            turn_doc={
                "question": next_out.question,
                "answer": "",
                "timestamp": datetime.utcnow(),
                "mode": next_out.mode,
                "questionId": next_out.questionId,
            },
        )

        # Speech stats for this answer
        stats = compute_speech_stats(transcript=transcript, audio_duration_ms=audio_duration_ms)

        # TTS for next question
        tts_res = await self._tts.synthesize_speech(text=next_out.question)

        # The next question is already appended above, so update the known
        # answered index. Updating the "last" item here would incorrectly put
        # speech data on the next, unanswered question.
        try:
            await self.mongo.update_conversation_turn(
                session_id=session_id,
                turn_index=answered_turn_index,
                overlay={
                    "transcript": transcript,
                    "audioDurationMs": audio_duration_ms,
                    "fillerWordCount": stats.filler_word_count,
                    "wpm": stats.wpm,
                    "avgPauseLengthS": stats.avg_pause_length_s,
                    "verbalConfidence": stats.verbal_confidence,
                    "submittedAt": datetime.utcnow(),
                },
            )

        except Exception:
            pass


        return InterviewTurnOutVoice(
            question=next_out.question,
            response=next_out.response,
            mode=next_out.mode,
            questionId=next_out.questionId,
            turnIndex=next_out.turnIndex,
            questionAudioB64=tts_res.audio_b64 if tts_res else None,
            questionAudioMimeType=tts_res.mime_type if tts_res else None,
            transcript=transcript,
            audioDurationMs=audio_duration_ms,
            fillerWordCount=stats.filler_word_count,
            wpm=stats.wpm,
            avgPauseLengthS=stats.avg_pause_length_s,
            verbalConfidence=stats.verbal_confidence,
            responseScore=next_out.responseScore,
            receivedAt=datetime.utcnow(),
        )

