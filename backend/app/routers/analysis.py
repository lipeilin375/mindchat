from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.emotion_analysis import EmotionAnalysis
from app.models.audio_record import AudioRecord
from app.schemas.analysis import AnalysisListResponse, AnalysisResponse, AnalysisListItem
from app.services.analysis_service import process_voice_analysis
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings

router = APIRouter()


@router.post("/upload", response_model=AnalysisResponse, summary="上传语音并触发分析")
async def upload_audio(
    file: UploadFile = File(..., description="音频文件（支持 webm/wav/mp3/ogg/m4a 等）"),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """
    接收用户上传的录音文件，执行：
    1. 转码为 MP3 保存
    2. Whisper 语音转文字
    3. LLM 情绪 + 抑郁倾向分析
    4. 持久化结果并按需生成预警
    """
    # File size guard (read content-length header if present)
    max_bytes = settings.MAX_AUDIO_SIZE_MB * 1024 * 1024
    # We rely on ffmpeg to reject truly invalid files; size check via file_size after save

    return await process_voice_analysis(file, current_user.id, db)


@router.get("/history", response_model=AnalysisListResponse, summary="获取当前用户历史分析")
def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = db.query(EmotionAnalysis).filter(
        EmotionAnalysis.user_id == current_user.id
    )
    total = base_query.count()

    rows = (
        db.query(EmotionAnalysis)
        .filter(EmotionAnalysis.user_id == current_user.id)
        .order_by(EmotionAnalysis.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    items = [
        AnalysisListItem(
            analysis_id=r.id,
            record_id=r.record_id,
            primary_emotion=r.primary_emotion,
            depression_level=r.depression_level,
            phq_score=r.phq_score,
            created_at=r.created_at,
        )
        for r in rows
    ]
    return {
        "total": total,
        "items": items
    }


@router.get("/{analysis_id}", response_model=AnalysisResponse, summary="获取单条分析详情")
def get_analysis_detail(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    analysis = (
        db.query(EmotionAnalysis)
        .filter(
            EmotionAnalysis.id == analysis_id,
            EmotionAnalysis.user_id == current_user.id,
        )
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")

    record = db.query(AudioRecord).filter(AudioRecord.id == analysis.record_id).first()
    return AnalysisResponse.from_orm_objects(record, analysis)