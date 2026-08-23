from fastapi import APIRouter

from app.api.routers.resume import router as resume_router
from app.api.routers.health import router as health_router
from app.api.routers.interview_ws import router as interview_ws_router
from app.api.routers.evaluate_code import router as evaluate_code_router


api_router = APIRouter()
api_router.include_router(health_router)
api_router.include_router(resume_router)
api_router.include_router(interview_ws_router)
api_router.include_router(evaluate_code_router)

from app.api.routers.emotion import router as emotion_router
api_router.include_router(emotion_router)

from app.api.routers.scoring import router as scoring_router
api_router.include_router(scoring_router)

from app.api.routers.report import router as report_router
api_router.include_router(report_router)

from app.api.routers.logs import router as logs_router
api_router.include_router(logs_router)














