import uuid
from sqlalchemy.orm import Session
from fastapi import HTTPException, status

from app.agents.tools.security_tools import analyze_message
from app.models.security_analysis import SecurityAnalysis
from app.repositories.user_repository import UserRepository
from app.schemas.security import SecurityAnalyzeRequest, SecurityAnalyzeResponse


class SecurityService:
    """Digital Shield service analyzing user-submitted messages for scam/phishing indicators.

    Results are persisted in the database (they survive restarts) together with their owner.
    The raw message text is never stored — only the analysis.
    """

    def __init__(self, db: Session):
        self.db = db
        self.user_repo = UserRepository(db)

    @staticmethod
    def _to_response(row: SecurityAnalysis) -> SecurityAnalyzeResponse:
        return SecurityAnalyzeResponse(
            analysis_id=row.id,
            risk_level=row.risk_level,  # type: ignore[arg-type]
            risk_score=row.risk_score,
            indicators=list(row.indicators or []),
            explanation=row.explanation,
            recommendation=row.recommendation,
        )

    def analyze(self, request: SecurityAnalyzeRequest, user_id: str) -> SecurityAnalyzeResponse:
        result = analyze_message(request.message)
        row = SecurityAnalysis(
            id=str(uuid.uuid4()),
            user_id=user_id,
            risk_level=result["risk_level"],
            risk_score=result["risk_score"],
            indicators=result["indicators"],
            explanation=result["explanation"],
            recommendation=result["recommendation"],
        )
        self.db.add(row)
        self.db.commit()
        self.db.refresh(row)

        self.user_repo.log_agent_event(user_id=user_id, intent="ANALYZE_MESSAGE", status="completed")
        return self._to_response(row)

    def get_result(self, analysis_id: str, user_id: str) -> SecurityAnalyzeResponse:
        row = (
            self.db.query(SecurityAnalysis)
            .filter(SecurityAnalysis.id == analysis_id, SecurityAnalysis.user_id == user_id)
            .first()
        )
        if row is None:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail="Analiz nəticəsi tapılmadı.",
            )
        return self._to_response(row)
