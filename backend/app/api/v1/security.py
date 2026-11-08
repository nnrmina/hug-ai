from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

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
    db: Session = Depends(get_db),
):
    service = SecurityService(db)
    return service.analyze(request)


@router.get(
    "/security/result/{analysis_id}",
    response_model=SecurityAnalyzeResponse,
)
async def get_security_analysis_result(
    analysis_id: str,
    db: Session = Depends(get_db),
):
    service = SecurityService(db)
    return service.get_result(analysis_id)

