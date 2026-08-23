from pydantic import BaseModel
from fastapi import APIRouter, Depends, HTTPException
from app.api.auth import require_auth

from app.core.config import get_settings
from app.schemas.resume import ParsedResumeResponse
from app.services.resume_parser import parse_resume_from_url


router = APIRouter()


class ResumeParseRequest(BaseModel):
    file_url: str


@router.post("/parse-resume", response_model=ParsedResumeResponse)
def parse_resume(request: ResumeParseRequest, _user: dict = Depends(require_auth)) -> ParsedResumeResponse:
    settings = get_settings()

    try:
        return parse_resume_from_url(request.file_url, settings)
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error)) from error
    except Exception as error:
        raise HTTPException(
            status_code=500,
            detail="Could not parse the resume file. Make sure it is a valid PDF or DOCX.",
        ) from error
