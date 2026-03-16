# Import all models so that SQLAlchemy can discover them for table creation
from app.models.user import User
from app.models.audio_record import AudioRecord
from app.models.emotion_analysis import EmotionAnalysis
from app.models.alert import Alert

__all__ = ["User", "AudioRecord", "EmotionAnalysis", "Alert"]