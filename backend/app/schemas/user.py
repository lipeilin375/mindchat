from pydantic import BaseModel, Field
from datetime import datetime


class UserProfileUpdate(BaseModel):
    gender: str | None = None
    age: int | None = Field(None, ge=1, le=120)
    phone: str | None = None


class ChangePasswordUpdate(BaseModel):
    state: bool | None = None


class UserProfile(BaseModel):
    id: int
    username: str
    role: str
    gender: str | None
    age: int | None
    phone: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class ChangePassword(BaseModel):
    old_password: str
    new_password: str


class AdminUserListItem(BaseModel):
    id: int
    username: str
    role: str
    gender: str | None
    age: int | None
    phone: str | None
    is_active: bool
    created_at: datetime

    class Config:
        from_attributes = True


class AdminUserStatusUpdate(BaseModel):
    is_active: bool