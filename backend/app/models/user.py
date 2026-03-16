from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.orm import relationship
from sqlalchemy.sql import func
from app.database import Base


class User(Base):
    __tablename__ = "users"

    id               = Column(Integer, primary_key=True, index=True, autoincrement=True)
    username         = Column(String(50), unique=True, nullable=False, index=True)
    hashed_password  = Column(String(255), nullable=False)
    role             = Column(String(10), nullable=False, default="user")   # user | admin
    gender           = Column(String(10), nullable=True)
    age              = Column(Integer, nullable=True)
    phone            = Column(String(20), nullable=True)
    is_active        = Column(Boolean, default=True)
    created_at       = Column(DateTime(timezone=True), server_default=func.now())
    updated_at       = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())

    # Relationships
    audio_records    = relationship(
        "AudioRecord",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    emotion_analyses = relationship(
        "EmotionAnalysis",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    alerts           = relationship(
        "Alert",
        back_populates="user",
        foreign_keys="[Alert.user_id]",
        primaryjoin="User.id == Alert.user_id",
        cascade="all, delete-orphan",
    )