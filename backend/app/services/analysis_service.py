import json
import logging
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session

from app.models.audio_record import AudioRecord
from app.models.emotion_analysis import EmotionAnalysis
from app.models.alert import Alert
from app.utils.audio import save_audio_as_mp3
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import analyze_emotion, analyze_mental_data
from app.schemas.analysis import AnalysisResponse

logger = logging.getLogger(__name__)

# PHQ score → depression level mapping
PHQ_LEVEL_MAP = [
    (10, "none"),       # 0-4
    (5,  "none"),       # duplicate guard
    (10, "mild"),       # 5-9  → handled below
    (15, "moderate"),
    (28, "severe"),
]


def _phq_to_level(score: int) -> str:
    if score <= 4:
        return "none"
    elif score <= 9:
        return "mild"
    elif score <= 14:
        return "moderate"
    else:
        return "severe"


def _alert_for_level(level: str) -> tuple[str, str] | None:
    """Return (alert_level, message) or None if no alert needed."""
    if level == "moderate":
        return ("warning", "检测到中度抑郁倾向，建议寻求专业心理辅导。")
    elif level == "severe":
        return ("critical", "检测到重度抑郁倾向，强烈建议立即联系专业心理医生！")
    return None


async def process_voice_analysis(
    file: UploadFile,
    user_id: int,
    db: Session,
) -> AnalysisResponse:
    """
    Full pipeline:
      1. Save audio → convert to MP3
      2. Whisper transcription
      3. LLM emotion + depression analysis
      4. Persist results
      5. Generate alert if needed
    """

    # ── Step 1: Save as MP3 ────────────────────────────────────────────────
    try:
        file_info = await save_audio_as_mp3(file, user_id)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))

    record = AudioRecord(
        user_id=user_id,
        file_path=file_info["file_path"],
        file_name=file_info["file_name"],
        file_size=file_info["file_size"],
        mime_type=file_info["mime_type"],
        status="processing",
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        # ── Step 2: Whisper ──────────────────────────────────────────────────
        logger.info(f"Transcribing record {record.id} for user {user_id}")
        transcription_result = await transcribe_audio(file_info["file_path"])
        transcription_text   = transcription_result["text"]

        record.transcription = transcription_text
        record.status = "transcribed"
        db.commit()

        if not transcription_text.strip():
            raise ValueError("转录结果为空，请确保录音内容清晰。")

        # ── Step 3: LLM analysis ─────────────────────────────────────────────
        logger.info(f"Running LLM analysis for record {record.id}")
        analysis_data = await analyze_emotion(record.file_path, transcription_text)
        mental_data = await analyze_mental_data(transcription_text, json.dumps(analysis_data.get("probs", {}), ensure_ascii=False))

        # Normalise depression_level using phq_score as ground truth
        phq_score = int(mental_data.get("phq_score") or 0)
        depression_level = mental_data.get("depression_level") or _phq_to_level(phq_score)

        # ── Step 4: Persist ──────────────────────────────────────────────────
        analysis = EmotionAnalysis(
            record_id=record.id,
            user_id=user_id,
            primary_emotion=analysis_data.get("emotion"),
            emotion_scores=json.dumps(analysis_data.get("probs", {}), ensure_ascii=False),
            depression_level=depression_level,
            phq_score=phq_score,
            risk_factors=json.dumps(mental_data.get("risk_factors", []), ensure_ascii=False),
            llm_analysis=mental_data.get("llm_analysis"),
            suggestions=json.dumps(mental_data.get("suggestions", []), ensure_ascii=False),
        )
        db.add(analysis)
        record.status = "done"
        db.commit()
        db.refresh(analysis)

        # ── Step 5: Alert ────────────────────────────────────────────────────
        alert_info = _alert_for_level(depression_level)
        if alert_info:
            alert_level, alert_msg = alert_info
            db.add(Alert(
                user_id=user_id,
                analysis_id=analysis.id,
                level=alert_level,
                message=alert_msg,
            ))
            db.commit()

        logger.info(f"Analysis complete: record={record.id}, analysis={analysis.id}, phq={phq_score}")
        return AnalysisResponse.from_orm_objects(record, analysis)

    except Exception as e:
        record.status = "failed"
        record.error_msg = str(e)
        db.commit()
        logger.error(f"Analysis failed for record {record.id}: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail=f"分析失败: {e}")