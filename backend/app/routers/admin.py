from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.models.emotion_analysis import EmotionAnalysis
from app.models.alert import Alert
from app.schemas.user import AdminUserListItem, AdminUserListResponse, AdminUserStatusUpdate
from app.schemas.analysis import AlertListResponse, AlertResponse, AdminStatsResponse, AnalysisListResponse, AnalysisResponse, AnalysisListItem
from app.models.audio_record import AudioRecord
from app.dependencies import get_admin_user

router = APIRouter()


# ─────────────────────────────────────────────────────────────────────────────
# Dashboard Stats
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/stats", response_model=AdminStatsResponse, summary="统计数据汇总")
def get_stats(
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    total_users     = db.query(func.count(User.id)).filter(User.role == "user").scalar() or 0
    total_analyses  = db.query(func.count(EmotionAnalysis.id)).scalar() or 0
    unread_alerts   = db.query(func.count(Alert.id)).filter(Alert.is_read == False).scalar() or 0

    # Depression distribution
    dep_rows = (
        db.query(EmotionAnalysis.depression_level, func.count(EmotionAnalysis.id))
        .group_by(EmotionAnalysis.depression_level)
        .all()
    )
    depression_dist = {"none": 0, "mild": 0, "moderate": 0, "severe": 0}
    for level, cnt in dep_rows:
        if level and level in depression_dist:
            depression_dist[level] = cnt

    # Emotion distribution
    emotion_rows = (
        db.query(EmotionAnalysis.primary_emotion, func.count(EmotionAnalysis.id))
        .group_by(EmotionAnalysis.primary_emotion)
        .all()
    )
    emotion_dist: dict = {}
    for emotion, cnt in emotion_rows:
        if emotion:
            emotion_dist[emotion] = cnt

    return AdminStatsResponse(
        total_users=total_users,
        total_analyses=total_analyses,
        unread_alerts=unread_alerts,
        depression_distribution=depression_dist,
        emotion_distribution=emotion_dist,
    )


# ─────────────────────────────────────────────────────────────────────────────
# User Management
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/users", response_model=AdminUserListResponse, summary="用户列表")
def list_users(
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    search: str | None = Query(None, description="按用户名模糊搜索"),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    q = db.query(User).filter(User.role == "user")
    if search:
        q = q.filter(User.username.ilike(f"%{search}%"))
    total = q.count()
    rows = (
        q.order_by(User.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        AdminUserListItem.model_validate(r)
        for r in rows
    ]
    return {
        "total": total,
        "items": items
    }


@router.get("/users/{user_id}", response_model=AdminUserListItem, summary="用户详情")
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    return user


@router.put("/users/{user_id}/status", response_model=AdminUserListItem, summary="启用/禁用用户")
def update_user_status(
    user_id: int,
    payload: AdminUserStatusUpdate,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=404, detail="用户不存在")
    user.is_active = payload.is_active
    db.commit()
    db.refresh(user)
    return user


@router.get("/users/{user_id}/analyses", response_model=AnalysisListResponse, summary="指定用户的分析记录")
def get_user_analyses(
    user_id: int,
    skip: int = Query(0, ge=0),
    limit: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    q = db.query(EmotionAnalysis).filter(
        EmotionAnalysis.user_id == user_id
    )
    total = q.count()
    rows = (
        db.query(EmotionAnalysis)
        .filter(EmotionAnalysis.user_id == user_id)
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


@router.get("/users/{user_id}/analyses/{analysis_id}", response_model=AnalysisResponse, summary="分析详情（Admin视角）")
def get_analysis_detail_admin(
    user_id: int,
    analysis_id: int,
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    analysis = (
        db.query(EmotionAnalysis)
        .filter(EmotionAnalysis.id == analysis_id, EmotionAnalysis.user_id == user_id)
        .first()
    )
    if not analysis:
        raise HTTPException(status_code=404, detail="分析记录不存在")
    record = db.query(AudioRecord).filter(AudioRecord.id == analysis.record_id).first()
    return AnalysisResponse.from_orm_objects(record, analysis)


# ─────────────────────────────────────────────────────────────────────────────
# Alerts
# ─────────────────────────────────────────────────────────────────────────────

@router.get("/alerts", response_model=AlertListResponse, summary="预警列表")
def list_alerts(
    unread_only: bool = Query(False, description="只看未读"),
    skip: int = Query(0, ge=0),
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    _: User = Depends(get_admin_user),
):
    q = db.query(Alert)
    if unread_only:
        q = q.filter(Alert.is_read == False)
    total = q.count()
    rows = (
        q.order_by(Alert.created_at.desc())
        .offset(skip)
        .limit(limit)
        .all()
    )
    items = [
        AlertResponse.model_validate(r)
        for r in rows
    ]
    return {
        "total": total,
        "items": items
    }


@router.put("/alerts/{alert_id}/read", response_model=AlertResponse, summary="标记预警为已读")
def mark_alert_read(
    alert_id: int,
    db: Session = Depends(get_db),
    admin: User = Depends(get_admin_user),
):
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if not alert:
        raise HTTPException(status_code=404, detail="预警记录不存在")
    alert.is_read = True
    alert.read_by = admin.id
    db.commit()
    db.refresh(alert)
    return alert