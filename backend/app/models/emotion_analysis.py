from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class EmotionAnalysis(Base):
    __tablename__ = "emotion_analyses"

    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id        = Column(Integer, ForeignKey("audio_records.id", ondelete="CASCADE"), nullable=False, unique=True)
    user_id          = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # Emotion classification
    primary_emotion  = Column(String(30), nullable=True)   # joy|sadness|anger|fear|disgust|neutral
    emotion_scores   = Column(Text, nullable=True)          # JSON string

    # Depression assessment
    depression_level = Column(String(20), nullable=True)   # none|mild|moderate|severe
    phq_score        = Column(Integer, nullable=True)       # 0–27
    risk_factors     = Column(Text, nullable=True)          # JSON array string

    # LLM outputs
    llm_analysis     = Column(Text, nullable=True)
    suggestions      = Column(Text, nullable=True)          # JSON array string

    # Acoustic features (optional, filled if available)
    speech_rate      = Column(Float, nullable=True)         # words/min
    voice_energy     = Column(Float, nullable=True)
    pause_ratio      = Column(Float, nullable=True)

    created_at       = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    record           = relationship("AudioRecord",  back_populates="analysis")
    user             = relationship("User",         back_populates="emotion_analyses")
    alert            = relationship("Alert",        back_populates="analysis", uselist=False)


class AnalysisTask(Base):
    __tablename__ = "analysis_tasks"
 
    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    record_id   = Column(
        Integer,
        ForeignKey("audio_records.id", ondelete="CASCADE"),
        nullable=False,
        unique=True,
        index=True,
    )
    user_id     = Column(
        Integer,
        ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
 
    # Worker 通过 file_path + transcription 做分析，不需要再查 audio_records
    file_path   = Column(String(512), nullable=False)
 
    # 任务状态：pending → processing → done / failed
    status      = Column(String(20), default="pending", index=True)
    error_msg   = Column(Text, nullable=True)
 
    # 严格按 created_at 升序消费，保证先进先出
    created_at  = Column(DateTime(timezone=True), server_default=func.now(), index=True)
    updated_at  = Column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
    )
 
    # 关系（可选，方便 ORM 联查）
    record      = relationship("AudioRecord", backref="task", uselist=False)