from typing import List, Literal, Optional
from pydantic import BaseModel, Field


class SecurityAnalyzeRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000, description="Analiz ediləcək SMS və ya mesaj mətni")
    sender: Optional[str] = Field(default=None, max_length=100, description="Göndərən nömrə və ya ad (opsional)")


class SecurityAnalyzeResponse(BaseModel):
    analysis_id: str
    risk_level: Literal["low", "medium", "high"]
    risk_score: int = Field(..., ge=0, le=100)
    indicators: List[str]
    explanation: str
    recommendation: str

