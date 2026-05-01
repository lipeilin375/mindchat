from fastapi import APIRouter, Depends, UploadFile, File, HTTPException, Query
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.emotion_analysis import AnalysisTask, EmotionAnalysis
from app.models.audio_record import AudioRecord
from app.schemas.analysis import AnalysisListResponse, AnalysisResponse, AnalysisListItem, TaskAcceptedResponse
# from app.services.analysis_service import process_voice_analysis
from app.dependencies import get_current_user
from app.models.user import User
from app.config import settings

from app.utils.audio import save_audio_as_mp3

router = APIRouter()


@router.post(
    "/upload",
    response_model=TaskAcceptedResponse,
    status_code=202,
    summary="上传语音（异步分析）",
)
async def upload_audio(
    file: UploadFile = File(..., description="音频文件（支持 webm/wav/mp3/ogg/m4a 等）"),
    db: Session = Depends(get_db),
    current_user=Depends(get_current_user),
):
    try:
        file_info = await save_audio_as_mp3(file, current_user.id)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
 
    # ── 2. 写 audio_records（status=pending） ──────────────────────────────
    record = AudioRecord(
        user_id   = current_user.id,
        file_path = file_info["file_path"],
        file_name = file_info["file_name"],
        file_size = file_info["file_size"],
        mime_type = file_info["mime_type"],
        status    = "pending",
    )
    db.add(record)
    db.flush()          # 获得 record.id，尚未 commit
 
    # ── 3. 写 analysis_tasks（status=pending） ─────────────────────────────
    task = AnalysisTask(
        record_id = record.id,
        user_id   = current_user.id,
        file_path = file_info["file_path"],
        status    = "pending",
    )
    db.add(task)
    db.commit()
    db.refresh(record)
    db.refresh(task)
 
    # ── 4. 立即返回 202 ────────────────────────────────────────────────────
    return TaskAcceptedResponse(
        record_id = record.id,
        task_id   = task.id,
        status    = "pending",
        message   = "录音已接收，正在排队分析，请稍后查询结果。",
    )


@router.get("/history", response_model=AnalysisListResponse, summary="获取当前用户历史分析")
def get_history(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    base_query = (
        db.query(AudioRecord)
        .filter(
            AudioRecord.user_id == current_user.id,
            AudioRecord.status  != "failed",        # 过滤失败记录
        )
    )
    total = base_query.count()

    records = (
        base_query
        .order_by(AudioRecord.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )

    # 批量取出已完成的分析结果，避免 N+1
    record_ids = [r.id for r in records]
    analyses = {
        a.record_id: a
        for a in db.query(EmotionAnalysis)
        .filter(EmotionAnalysis.record_id.in_(record_ids))
        .all()
    }

    items = [
        AnalysisListItem(
            analysis_id      = analyses[r.id].id if r.id in analyses else None,
            record_id        = r.id,
            primary_emotion  = analyses[r.id].primary_emotion  if r.id in analyses else None,
            depression_level = analyses[r.id].depression_level if r.id in analyses else None,
            phq_score        = analyses[r.id].phq_score        if r.id in analyses else None,
            status           = r.status,
            created_at       = r.created_at,
        )
        for r in records
    ]
    return {"total": total, "items": items}


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