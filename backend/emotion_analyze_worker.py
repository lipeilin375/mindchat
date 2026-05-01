import json
import logging
import os
import time

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session

# ── 将项目根加入 sys.path，让相对 import 生效 ──────────────────────────────
import sys
sys.path.insert(0, os.path.dirname(__file__))

from app.models.audio_record import AudioRecord
from app.models.emotion_analysis import AnalysisTask, EmotionAnalysis
from app.models.alert import Alert
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import analyze_emotion, analyze_mental_data
from app.config import settings

# ─────────────────────────────────────────────────────────────────────────────
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [WORKER] %(levelname)s %(message)s",
)
logger = logging.getLogger(__name__)

POLL_INTERVAL = int(os.getenv("POLL_INTERVAL_SEC", "3"))

# ── 数据库引擎（Worker 用同一个连接字符串）────────────────────────────────
engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False} if "sqlite" in settings.DATABASE_URL else {},
    pool_pre_ping=True,
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


# ─────────────────────────────────────────────────────────────────────────────
# 辅助函数
# ─────────────────────────────────────────────────────────────────────────────

def _phq_to_level(score: int) -> str:
    if score <= 4:  return "none"
    if score <= 9:  return "mild"
    if score <= 14: return "moderate"
    return "severe"


def _alert_for_level(level: str):
    mapping = {
        "mild":     ("info",    "检测到轻度抑郁倾向，建议关注情绪变化。"),
        "moderate": ("warning", "检测到中度抑郁倾向，建议寻求专业支持。"),
        "severe":   ("critical","检测到重度抑郁倾向，请立即联系专业人士。"),
    }
    return mapping.get(level)


# ─────────────────────────────────────────────────────────────────────────────
# 核心：处理单条任务
# ─────────────────────────────────────────────────────────────────────────────

import asyncio

async def _process_task(task: AnalysisTask, db: Session) -> None:
    """处理一条 pending 任务，结果写回数据库。"""
    record: AudioRecord = db.query(AudioRecord).filter(
        AudioRecord.id == task.record_id
    ).first()

    if not record:
        logger.error(f"Task {task.id}: record {task.record_id} not found, skipping.")
        task.status   = "failed"
        task.error_msg = "audio_record not found"
        db.commit()
        return

    try:
        # ── 标记"处理中" ───────────────────────────────────────────────────
        task.status   = "processing"
        record.status = "processing"
        db.commit()

        # ── Step 1: Whisper 转录 ───────────────────────────────────────────
        logger.info(f"Task {task.id}: transcribing {task.file_path}")
        transcription_result = await transcribe_audio(task.file_path)
        transcription_text   = transcription_result["text"]

        record.transcription = transcription_text
        record.status        = "transcribed"
        db.commit()

        if not transcription_text.strip():
            raise ValueError("转录结果为空，请确保录音内容清晰。")

        # ── Step 2: LLM 情绪 + 抑郁分析 ──────────────────────────────────
        logger.info(f"Task {task.id}: running emotion analysis")
        analysis_data = await analyze_emotion(task.file_path, transcription_text)
        mental_data   = await analyze_mental_data(
            transcription_text,
            json.dumps(analysis_data.get("probs", {}), ensure_ascii=False),
        )

        phq_score        = int(mental_data.get("phq_score") or 0)
        depression_level = mental_data.get("depression_level") or _phq_to_level(phq_score)

        # ── Step 3: 写 emotion_analyses ───────────────────────────────────
        analysis = EmotionAnalysis(
            record_id        = record.id,
            user_id          = task.user_id,
            primary_emotion  = analysis_data.get("emotion"),
            emotion_scores   = json.dumps(analysis_data.get("probs", {}), ensure_ascii=False),
            depression_level = depression_level,
            phq_score        = phq_score,
            risk_factors     = json.dumps(mental_data.get("risk_factors", []), ensure_ascii=False),
            llm_analysis     = mental_data.get("llm_analysis"),
            suggestions      = json.dumps(mental_data.get("suggestions", []), ensure_ascii=False),
        )
        db.add(analysis)
        record.status = "done"
        task.status   = "done"
        db.flush()
        db.refresh(analysis)

        # ── Step 4: 预警 ──────────────────────────────────────────────────
        alert_info = _alert_for_level(depression_level)
        if alert_info:
            alert_level, alert_msg = alert_info
            db.add(Alert(
                user_id     = task.user_id,
                analysis_id = analysis.id,
                level       = alert_level,
                message     = alert_msg,
            ))

        db.commit()
        logger.info(
            f"Task {task.id} done: record={record.id}, phq={phq_score}, level={depression_level}"
        )

    except Exception as exc:
        db.rollback()
        record.status  = "failed"
        record.error_msg = str(exc)
        task.status    = "failed"
        task.error_msg = str(exc)
        db.commit()
        logger.error(f"Task {task.id} failed: {exc}", exc_info=True)


# ─────────────────────────────────────────────────────────────────────────────
# 轮询主循环
# ─────────────────────────────────────────────────────────────────────────────

async def run_worker() -> None:
    logger.info(f"Worker started. Poll interval: {POLL_INTERVAL}s")
    while True:
        db: Session = SessionLocal()
        try:
            # 取最早一条 pending 任务（严格 FIFO）
            task: AnalysisTask | None = (
                db.query(AnalysisTask)
                .filter(AnalysisTask.status == "pending")
                .order_by(AnalysisTask.created_at.asc())
                .with_for_update(skip_locked=True)   # 防止多 Worker 竞争同一条
                .first()
            )
            if task:
                await _process_task(task, db)
            else:
                # 队列为空，等待下一个轮询周期
                await asyncio.sleep(POLL_INTERVAL)
        except Exception as exc:
            logger.error(f"Worker loop error: {exc}", exc_info=True)
            await asyncio.sleep(POLL_INTERVAL)
        finally:
            db.close()


if __name__ == "__main__":
    asyncio.run(run_worker())