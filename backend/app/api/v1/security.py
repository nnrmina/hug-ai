from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.core.auth import get_current_user_id
from app.core.database import get_db
from app.schemas.security import (
    SecurityAnalyzeRequest,
    SecurityAnalyzeResponse,
)
from app.services.security_service import SecurityService

router = APIRouter()


@router.post(
    "/security/analyze",
    response_model=SecurityAnalyzeResponse,
)
async def analyze_suspicious_message(
    request: SecurityAnalyzeRequest,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return SecurityService(db).analyze(request, user_id=user_id)


@router.get(
    "/security/result/{analysis_id}",
    response_model=SecurityAnalyzeResponse,
)
async def get_security_analysis_result(
    analysis_id: str,
    user_id: str = Depends(get_current_user_id),
    db: Session = Depends(get_db),
):
    return SecurityService(db).get_result(analysis_id, user_id=user_id)
