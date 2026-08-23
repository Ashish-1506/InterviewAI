from __future__ import annotations


import subprocess
from datetime import datetime
from typing import Any

from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import require_auth

from app.core.config import get_settings
from app.schemas.evaluate_code import CodeEvaluationOut, CodeEvaluateRequest
from app.services.code_evaluator_ai import CodeEvaluatorAI
from app.services.code_sandbox import CodeSandboxRunner, SandboxLimits, CodeSecurityError
from app.services.question_bank import QuestionBankLoader
from app.services.mongo_store import MongoStore



router = APIRouter()


@router.post("/evaluate-code", response_model=CodeEvaluationOut)
async def evaluate_code(req: CodeEvaluateRequest, _user: dict[str, Any] = Depends(require_auth)) -> Any:
    settings = get_settings()

    # Mongo persistence (best-effort)
    # Note: Interview session storage lives in the Node backend, but FastAPI already uses MongoStore
    # for other state; so we keep using it here as well.
    mongo = MongoStore(settings=settings)

    loader = QuestionBankLoader(settings=settings)

    questions = loader.load()

    q = None
    for cand in questions:
        if str(cand.get("id") or cand.get("questionId")) == req.question_id:
            q = cand
            break

    if not q:
        raise HTTPException(status_code=404, detail="question_id not found")

    problem_spec = q.get("problemSpec") or q.get("hiddenTests")
    if not problem_spec or not isinstance(problem_spec, dict):
        raise HTTPException(status_code=400, detail="question is missing problemSpec.hiddenTests")

    hidden_tests = problem_spec.get("hiddenTests")
    entrypoint = problem_spec.get("entrypoint")

    if not hidden_tests or not isinstance(hidden_tests, list):
        raise HTTPException(status_code=400, detail="problemSpec.hiddenTests must be a list")
    if not entrypoint:
        raise HTTPException(status_code=400, detail="problemSpec.entrypoint is required")

    limits = SandboxLimits(timeout_seconds=8, memory_mb=256)
    runner = CodeSandboxRunner(limits=limits)

    started = datetime.utcnow()

    # ---- 1) Sandbox execution ----
    try:
        exec_payload = runner.run(language=req.language, code=req.code, entrypoint=str(entrypoint), hidden_tests=hidden_tests)
    except CodeSecurityError as se:
        finished = datetime.utcnow()
        return CodeEvaluationOut(
            question_id=req.question_id,
            passed=False,
            startedAt=started,
            finishedAt=finished,
            testResults=[],
            summary=f"Security policy violation: {se}",
            stdout=None,
            stderr=None,
            aiReview=None,
        )
    except subprocess.TimeoutExpired:
        finished = datetime.utcnow()
        return CodeEvaluationOut(
            question_id=req.question_id,
            passed=False,
            startedAt=started,
            finishedAt=finished,
            testResults=[],
            summary="Execution timed out",
            stdout=None,
            stderr=None,
            aiReview=None,
        )
    except Exception as e:
        finished = datetime.utcnow()
        raise HTTPException(status_code=500, detail=f"Execution failed: {e}")


    passed = bool(exec_payload.get("passed"))
    results = exec_payload.get("results") or []

    test_results = [
        {
            "input": r.get("input"),
            "expected": r.get("expected"),
            "actual": r.get("actual"),
            "passed": bool(r.get("passed")),
            "error": r.get("error"),
        }
        for r in results
    ]

    summary = "All tests passed" if passed else "One or more tests failed"

    stdout = exec_payload.get("stdout")
    stderr = exec_payload.get("stderr")

    finished = datetime.utcnow()

    # ---- 2) LLM qualitative review ----
    ai = CodeEvaluatorAI(settings=settings)

    # Keep statement short; question bank format varies.
    problem_text = q.get("question") or q.get("prompt") or q.get("description") or ""

    failed_cases = []
    for r in results:
        if not r.get("passed"):
            failed_cases.append({
                "input": r.get("input"),
                "expected": r.get("expected"),
                "actual": r.get("actual"),
                "error": r.get("error"),
            })

    test_summary = {
        "passed": passed,
        "summary": summary,
        "failedCases": failed_cases,
    }

    review = await ai.review(
        problem_text=str(problem_text),
        question_id=str(req.question_id),
        candidate_code=req.code,
        test_summary=test_summary,
    )

    # ---- 3) Persistence (submission linked to turn) ----
    turn_index = req.turnIndex
    submission_doc = {
        "language": req.language,
        "code": req.code,
        "passed": passed,
        "summary": summary,
        "stdout": stdout,
        "stderr": stderr,
        "aiReview": review.ai_review,
        "testResults": test_results,
        "questionId": req.question_id,
        "turnIndex": turn_index,
        "timestamp": finished,
    }

    # Best-effort: store on session under a new array if it doesn't exist.
    # For now, we append a synthetic conversation turn answer overlay.
    # (MongoStore currently doesn't have a dedicated method.)
    # We'll use update_one via append to conversationTurns by attaching an evaluation object.
    if turn_index is not None:
        # overlay the matching turn if exists
        await mongo.update_last_conversation_turn(
            session_id=req.session_id,
            overlay={
                "codeSubmission": submission_doc,
            },
        )
    else:
        await mongo.append_conversation_turn(
            session_id=req.session_id,
            turn_doc={
                "question": "(coding submission)",
                "answer": "(coding submission)",
                "timestamp": finished,
                "mode": "Technical",
                "questionId": req.question_id,
                "codeSubmission": submission_doc,
            },
        )

    return CodeEvaluationOut(
        question_id=req.question_id,
        passed=passed,
        startedAt=started,
        finishedAt=finished,
        testResults=test_results,
        summary=summary,
        stdout=stdout,
        stderr=stderr,
        aiReview=review.ai_review,
    )



