from sqlalchemy import Column, Integer, String, Float, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class AudioRecord(Base):
    __tablename__ = "audio_records"

    id            = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id       = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)

    # File info — always stored as mp3
    file_path     = Column(String(512), nullable=False)
    file_name     = Column(String(255), nullable=True)
    file_size     = Column(Integer, nullable=True)          # bytes
    duration      = Column(Float, nullable=True)            # seconds
    mime_type     = Column(String(50), default="audio/mpeg")

    # Processing
    transcription = Column(Text, nullable=True)             # Whisper output
    status        = Column(String(20), default="pending")   # pending|processing|done|failed
    error_msg     = Column(Text, nullable=True)

    created_at    = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user          = relationship("User",          back_populates="audio_records")
    analysis      = relationship("EmotionAnalysis", back_populates="record", uselist=False)