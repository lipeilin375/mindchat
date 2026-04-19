from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.database import get_db
from app.models.user import User
from app.schemas.user import UserProfile, UserProfileUpdate, ChangePassword, ChangePasswordUpdate
from app.utils.security import get_password_hash, verify_password
from app.dependencies import get_current_user

router = APIRouter()


@router.get("/profile", response_model=UserProfile)
def get_profile(current_user: User = Depends(get_current_user)):
    """获取当前用户个人资料"""
    return current_user


@router.put("/profile", response_model=UserProfile)
def update_profile(
    payload: UserProfileUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """更新当前用户个人资料（gender / age / phone）"""
    update_data = payload.model_dump(exclude_none=True)
    for field, value in update_data.items():
        setattr(current_user, field, value)
    db.commit()
    db.refresh(current_user)
    return current_user


@router.post("/changepassword", response_model=ChangePasswordUpdate)
def change_password(
    payload: ChangePassword,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """修改用户密码"""
    if not verify_password(payload.old_password, current_user.hashed_password):
        raise HTTPException(status_code=400, detail="原密码错误")
    current_user.hashed_password = get_password_hash(payload.new_password)
    update_data = payload.model_dump(exclude_none=True)
    update_data["state"] = True
    db.commit()
    db.refresh(current_user)
    return update_data