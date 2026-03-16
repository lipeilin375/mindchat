from pydantic import BaseModel, Field


class RegisterRequest(BaseModel):
    username: str = Field(..., min_length=3, max_length=50)
    password: str = Field(..., min_length=6, max_length=128)
    gender: str | None = None
    age: int | None = Field(None, ge=1, le=120)
    phone: str | None = None


class LoginRequest(BaseModel):
    username: str
    password: str


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: "UserInfo"


class UserInfo(BaseModel):
    id: int
    username: str
    role: str
    gender: str | None
    age: int | None
    phone: str | None
    is_active: bool

    class Config:
        from_attributes = True


TokenResponse.model_rebuild()