from __future__ import annotations

import asyncio
import base64
import json
import logging
from datetime import datetime
from typing import Any



from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.api.auth import authenticate_websocket

from app.core.config import get_settings
from app.schemas.interview_turn import InterviewTurnIn, InterviewTurnOut
from app.schemas.interview_voice import InterviewTurnOutVoice, InterviewVoiceTurnIn
from app.services.interviewer_engine import InterviewerEngine
from app.services.mongo_store import MongoStore
from app.services.interview_voice_engine import InterviewVoiceEngine


router = APIRouter()
logger = logging.getLogger(__name__)


async def _append_pending_turn(
    mongo: MongoStore,
    session_id: str,
    question: str,
    mode: str,
    question_id: str | None,
) -> None:
    await mongo.append_conversation_turn(
        session_id=session_id,
        turn_doc={
            "question": question,
            "answer": "",
            "timestamp": datetime.utcnow(),
            "mode": mode,
            "questionId": question_id,
        },
    )


@router.websocket("/ws/interview/{session_id}")
async def interview_ws(websocket: WebSocket, session_id: str):
    settings = get_settings()
    if not await authenticate_websocket(websocket):
        return
    await websocket.accept()

    mongo = MongoStore(settings=settings)
    engine = InterviewerEngine(settings=settings, mongo=mongo)
    voice_engine = InterviewVoiceEngine(settings=settings, mongo=mongo, interviewer=engine)

    # Warm the STT model in the background so a spoken answer does not stall the
    # next-question request on first use. Whisper is expensive to initialize and
    # should not happen on the first transcription request.
    try:
        asyncio.create_task(voice_engine._stt.warmup())
    except Exception:
        logger.exception("Failed to warmup STT provider for interview session %s", session_id)

    try:
        session_doc = await mongo.get_interview_session(session_id)
        if not session_doc:
            await websocket.send_json(
                InterviewTurnOut(
                    mode="HR",
                    question="Session not found.",
                    response=None,
                    questionId=None,
                    turnIndex=0,
                ).model_dump()
            )
            await websocket.close(code=1008)
            return

        # If there is no conversation yet, ask the first question (and TTS it).
        turns = session_doc.get("conversationTurns") or []
        if len(turns) == 0:
            first = await engine.get_next_question(
                session_doc=session_doc,
                interview_type=session_doc.get("type") or "HR",
                last_n_turns=[],
            )

            await _append_pending_turn(
                mongo=mongo,
                session_id=session_id,
                question=first.question,
                mode=first.mode,
                question_id=first.questionId,
            )

            # TTS first question
            tts_res = await voice_engine._tts.synthesize_speech(text=first.question)
            await websocket.send_json(
                InterviewTurnOutVoice(
                    question=first.question,
                    response=first.response,
                    mode=first.mode,
                    questionId=first.questionId,
                    turnIndex=first.turnIndex,
                    questionAudioB64=tts_res.audio_b64 if tts_res else None,
                    questionAudioMimeType=tts_res.mime_type if tts_res else None,
                    transcript=None,
                    audioDurationMs=None,
                    fillerWordCount=None,
                    wpm=None,
                    avgPauseLengthS=None,
                    verbalConfidence=None,
                    responseScore=first.responseScore,
                ).model_dump()
            )
        else:
            # A browser refresh or a previous voice-provider failure can leave
            # a persisted question that the client never received. Replay that
            # unanswered prompt rather than leaving a reconnected interview
            # with no visible first question.
            pending_turn = turns[-1]
            pending_question = str(pending_turn.get("question") or "").strip()
            pending_answer = str(pending_turn.get("answer") or "").strip()
            if pending_question and not pending_answer:
                tts_res = await voice_engine._tts.synthesize_speech(text=pending_question)
                await websocket.send_json(
                    InterviewTurnOutVoice(
                        question=pending_question,
                        response=None,
                        mode=pending_turn.get("mode") or session_doc.get("type") or "HR",
                        questionId=pending_turn.get("questionId") or pending_turn.get("question_id"),
                        turnIndex=len(turns) - 1,
                        questionAudioB64=tts_res.audio_b64 if tts_res else None,
                        questionAudioMimeType=tts_res.mime_type if tts_res else None,
                        transcript=None,
                        audioDurationMs=None,
                        fillerWordCount=None,
                        wpm=None,
                        avgPauseLengthS=None,
                        verbalConfidence=None,
                        responseScore=None,
                    ).model_dump()
                )

        # In-memory audio buffer per websocket turn.
        # We accumulate chunk bytes until we receive `control: stop`.
        audio_buffer: list[bytes] = []
        recording_started_at_ms: int | None = None

        while True:
            raw = await websocket.receive_text()
            payload = json.loads(raw)

            # Two supported message types:
            # 1) Text-based legacy: {"answer": "..."}
            # 2) Voice-based: {"audio": {"audio_b64": "..."}, "control": {...}}

            if "answer" in payload:
                # Reset any in-progress buffers.
                audio_buffer = []
                recording_started_at_ms = None

                turn_in = InterviewTurnIn.model_validate(payload)
                next_out = await engine.process_candidate_answer(
                    session_id=session_id,
                    answer=turn_in.answer,
                    received_at=datetime.utcnow(),
                )

                await _append_pending_turn(
                    mongo=mongo,
                    session_id=session_id,
                    question=next_out.question,
                    mode=next_out.mode,
                    question_id=next_out.questionId,
                )

                # TTS next question
                tts_res = await voice_engine._tts.synthesize_speech(text=next_out.question)
                await websocket.send_json(
                    InterviewTurnOutVoice(
                        question=next_out.question,
                        response=next_out.response,
                        mode=next_out.mode,
                        questionId=next_out.questionId,
                        turnIndex=next_out.turnIndex,
                        questionAudioB64=tts_res.audio_b64 if tts_res else None,
                        questionAudioMimeType=tts_res.mime_type if tts_res else None,
                        transcript=turn_in.answer,
                        audioDurationMs=0,
                        fillerWordCount=None,
                        wpm=None,
                        avgPauseLengthS=None,
                        verbalConfidence=None,
                        responseScore=next_out.responseScore,
                    ).model_dump()
                )
                continue

            voice_in = InterviewVoiceTurnIn.model_validate(payload)

            # Start recording: reset buffer.
            if voice_in.control and voice_in.control.action == "start":
                audio_buffer = []
                recording_started_at_ms = datetime.utcnow().timestamp() * 1000
                continue


            # Streaming chunk: append bytes.
            if voice_in.audio and voice_in.audio.audio_b64:
                if recording_started_at_ms is None:
                    recording_started_at_ms = datetime.utcnow().timestamp() * 1000

                audio_buffer.append(base64.b64decode(voice_in.audio.audio_b64))
                continue

            # Stop: finalize and transcribe.
            if voice_in.control and voice_in.control.action == "stop":
                if not audio_buffer:
                    await websocket.send_json(
                        InterviewTurnOutVoice(
                            question="",
                            response=None,
                            mode=session_doc.get("type") or "HR",
                            questionId=None,
                            turnIndex=0,
                        ).model_dump()
                    )
                    continue

                # Best-effort duration from chunk timestamps if provided. If not, fall back to 0.
                # We don't currently compute accurate duration from container metadata.
                try:
                    # When using MediaRecorder(timeslice), the client provides chunk_start/end.
                    # We'll approximate total duration by last_end_ms - first_start_ms.
                    # (We didn't keep those values in buffer; so just set 0 for now.)
                    audio_duration_ms = 0
                except Exception:
                    audio_duration_ms = 0

                combined_bytes = b"".join(audio_buffer)
                transcript_out = await voice_engine.transcribe_audio_bytes(audio_bytes=combined_bytes, mime_type=None)



                session_doc = await mongo.get_interview_session(session_id)
                next_voice_out = await voice_engine.handle_candidate_transcript(
                    session_doc=session_doc,
                    session_id=session_id,
                    transcript=transcript_out.transcript,
                    audio_duration_ms=transcript_out.audio_duration_ms,
                )
                # ``receivedAt`` is a datetime on the voice response. Use
                # Pydantic's JSON mode so it is encoded as an ISO timestamp
                # instead of closing the socket with a TypeError.
                await websocket.send_json(next_voice_out.model_dump(mode="json"))

                # Reset for next turn.
                audio_buffer = []
                recording_started_at_ms = None
                continue

            # Ignore other messages.

    except WebSocketDisconnect:
        return
    except Exception:
        logger.exception("Interview WebSocket failed for session %s", session_id)
        try:
            await websocket.send_json(
                InterviewTurnOut(
                    mode="HR",
                    question="Something went wrong. Please try again.",
                    response=None,
                    questionId=None,
                    turnIndex=0,
                ).model_dump()
            )
        except Exception:
            pass
        try:
            await websocket.close(code=1011, reason="Interview service error")
        except Exception:
            pass


