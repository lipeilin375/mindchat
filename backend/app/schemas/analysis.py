from pydantic import BaseModel
from datetime import datetime
import json


class AnalysisResponse(BaseModel):
    record_id: int
    analysis_id: int
    transcription: str | None
    primary_emotion: str | None
    emotion_scores: dict | None
    depression_level: str | None
    phq_score: int | None
    risk_factors: list[str]
    llm_analysis: str | None
    suggestions: list[str]
    created_at: datetime

    class Config:
        from_attributes = True

    @classmethod
    def from_orm_objects(cls, record, analysis) -> "AnalysisResponse":
        def _parse(val, default):
            if val is None:
                return default
            if isinstance(val, str):
                try:
                    return json.loads(val)
                except Exception:
                    return default
            return val

        return cls(
            record_id=record.id,
            analysis_id=analysis.id,
            transcription=record.transcription,
            primary_emotion=analysis.primary_emotion,
            emotion_scores=_parse(analysis.emotion_scores, {}),
            depression_level=analysis.depression_level,
            phq_score=analysis.phq_score,
            risk_factors=_parse(analysis.risk_factors, []),
            llm_analysis=analysis.llm_analysis,
            suggestions=_parse(analysis.suggestions, []),
            created_at=analysis.created_at,
        )


class AnalysisListItem(BaseModel):
    analysis_id: int
    record_id: int
    primary_emotion: str | None
    depression_level: str | None
    phq_score: int | None
    created_at: datetime

    class Config:
        from_attributes = True


class AlertResponse(BaseModel):
    id: int
    user_id: int
    analysis_id: int | None
    level: str
    message: str | None
    is_read: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminStatsResponse(BaseModel):
    total_users: int
    total_analyses: int
    unread_alerts: int
    depression_distribution: dict   # {none: N, mild: N, moderate: N, severe: N}
    emotion_distribution: dict      # {joy: N, sadness: N, ...}