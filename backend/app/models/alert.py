from sqlalchemy import Column, Integer, String, Boolean, Text, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id          = Column(Integer, primary_key=True, index=True, autoincrement=True)
    user_id     = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    analysis_id = Column(Integer, ForeignKey("emotion_analyses.id", ondelete="SET NULL"), nullable=True)

    level       = Column(String(20), nullable=False)   # warning | urgent | critical
    message     = Column(Text, nullable=True)
    is_read     = Column(Boolean, default=False)
    read_by     = Column(Integer, ForeignKey("users.id"), nullable=True)  # admin user id

    created_at  = Column(DateTime(timezone=True), server_default=func.now())

    # Relationships
    user     = relationship(
        "User",
        back_populates="alerts",
        foreign_keys="[Alert.user_id]",
    )
    analysis = relationship("EmotionAnalysis", back_populates="alert")