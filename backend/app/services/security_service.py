import uuid
from typing import Dict
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.agents.tools.security_tools import analyze_message
from app.models.user import DEFAULT_USER_ID
from app.repositories.user_repository import UserRepository
from app.schemas.security import SecurityAnalyzeRequest, SecurityAnalyzeResponse

# Ephemeral in-memory cache of security analysis results (never stores raw sensitive message in DB)
_SECURITY_RESULTS: Dict[str, SecurityAnalyzeResponse] = {}


class SecurityService:
    """Digital Shield service analyzing user-submitted messages for scam/phishing indicators."""

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    def analyze(self, request: SecurityAnalyzeRequest) -> SecurityAnalyzeResponse:
        result = analyze_message(request.message)
        analysis_id = str(uuid.uuid4())

        response = SecurityAnalyzeResponse(
            analysis_id=analysis_id,
            risk_level=result["risk_level"],
            risk_score=result["risk_score"],
            indicators=result["indicators"],
            explanation=result["explanation"],
            recommendation=result["recommendation"],
        )
        _SECURITY_RESULTS[analysis_id] = response

        self.user_repo.log_agent_event(
            user_id=DEFAULT_USER_ID,
            intent="ANALYZE_MESSAGE",
            status="completed",
        )
        return response

    def get_result(self, analysis_id: str) -> SecurityAnalyzeResponse:
        if analysis_id not in _SECURITY_RESULTS:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analiz nəticəsi tapılmadı.",
            )
        return _SECURITY_RESULTS[analysis_id]

