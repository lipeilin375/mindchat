# 语音情绪分析与抑郁倾向识别系统 — 技术开发细节

---

## 目录

1. [项目概述](#1-项目概述)
2. [系统架构设计](#2-系统架构设计)
3. [目录结构](#3-目录结构)
4. [数据库设计（SQLite）](#4-数据库设计sqlite)
5. [后端开发（FastAPI）](#5-后端开发fastapi)
6. [前端开发（Vue 3）](#6-前端开发vue-3)
7. [语音处理与AI分析模块](#7-语音处理与ai分析模块)
8. [API接口文档](#8-api接口文档)
9. [认证与权限设计](#9-认证与权限设计)
10. [部署方案](#10-部署方案)

---

## 1. 项目概述

### 功能模块

| 模块 | 描述 |
|------|------|
| 用户端 | 语音录制、情绪历史查看、个人报告、预警提示 |
| Admin端 | 用户管理、数据统计大盘、高风险用户预警、分析记录审核 |

### 技术选型汇总

| 层级 | 技术栈 |
|------|--------|
| 前端 | Vue 3 + Vite + Pinia + Vue Router + Axios + Element Plus |
| 后端 | Python 3.11 + FastAPI + SQLAlchemy + Alembic |
| 数据库 | SQLite（开发/单机）|
| 语音转文字 | Whisper（本地 GGUF / OpenAI API）|
| 情绪分析 | 本地 Ollama（Qwen3:8B）或 OpenAI API |
| 认证 | JWT（python-jose）|
| 文件存储 | 本地文件系统 `/uploads/audio/` |
| 异步任务 | FastAPI BackgroundTasks（轻量）/ Celery+Redis（重量）|

---

## 2. 系统架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                        前端 (Vue 3)                          │
│   ┌──────────────┐          ┌──────────────────────────┐    │
│   │   用户端      │          │       Admin 管理端        │    │
│   │ /user/*      │          │       /admin/*            │    │
│   └──────┬───────┘          └────────────┬─────────────┘    │
└──────────┼──────────────────────────────┼──────────────────┘
           │  HTTP/REST (Axios)            │
           ▼                              ▼
┌─────────────────────────────────────────────────────────────┐
│                  FastAPI 后端服务 (:8000)                     │
│                                                             │
│  ┌─────────────┐  ┌──────────────┐  ┌──────────────────┐  │
│  │  Auth 模块   │  │  用户 API    │  │   Admin API      │  │
│  │ /auth/*     │  │  /user/*     │  │   /admin/*       │  │
│  └─────────────┘  └──────────────┘  └──────────────────┘  │
│                                                             │
│  ┌─────────────────────────────────────────────────────┐   │
│  │              语音分析 Pipeline                        │   │
│  │  音频上传 → Whisper转录 → 情绪分析(LLM) → PHQ评分    │   │
│  └─────────────────────────────────────────────────────┘   │
│                                                             │
│  ┌──────────────────┐    ┌───────────────────────────────┐ │
│  │  SQLAlchemy ORM  │    │  本地文件存储 /uploads/audio/  │ │
│  └────────┬─────────┘    └───────────────────────────────┘ │
└───────────┼─────────────────────────────────────────────────┘
            │
            ▼
┌───────────────────┐
│   SQLite DB       │
│  emotion_app.db   │
└───────────────────┘
```

---

## 3. 目录结构

### 后端目录

```
backend/
├── app/
│   ├── __init__.py
│   ├── main.py                  # FastAPI 入口
│   ├── config.py                # 配置管理（Settings）
│   ├── database.py              # SQLAlchemy engine & session
│   ├── dependencies.py          # 公共依赖（get_db, get_current_user）
│   │
│   ├── models/                  # SQLAlchemy ORM 模型
│   │   ├── user.py
│   │   ├── analysis.py
│   │   ├── audio_record.py
│   │   └── alert.py
│   │
│   ├── schemas/                 # Pydantic 请求/响应模型
│   │   ├── user.py
│   │   ├── analysis.py
│   │   └── auth.py
│   │
│   ├── routers/                 # 路由层
│   │   ├── auth.py
│   │   ├── user.py
│   │   ├── analysis.py
│   │   └── admin.py
│   │
│   ├── services/                # 业务逻辑层
│   │   ├── auth_service.py
│   │   ├── analysis_service.py  # 核心：语音→情绪分析
│   │   ├── whisper_service.py   # Whisper 转录
│   │   ├── llm_service.py       # LLM 情绪/抑郁分析
│   │   └── alert_service.py     # 预警逻辑
│   │
│   └── utils/
│       ├── audio.py             # 音频文件处理
│       ├── security.py          # JWT 工具
│       └── phq_scorer.py        # PHQ-9 评分算法
│
├── alembic/                     # 数据库迁移
│   └── versions/
├── uploads/
│   └── audio/
├── tests/
├── requirements.txt
├── alembic.ini
└── .env
```

### 前端目录

```
frontend/
├── src/
│   ├── main.ts
│   ├── App.vue
│   ├── router/
│   │   └── index.ts             # 路由配置（含路由守卫）
│   │
│   ├── stores/                  # Pinia 状态管理
│   │   ├── auth.ts
│   │   ├── analysis.ts
│   │   └── admin.ts
│   │
│   ├── api/                     # Axios 封装
│   │   ├── request.ts           # axios 实例 + 拦截器
│   │   ├── auth.ts
│   │   ├── analysis.ts
│   │   └── admin.ts
│   │
│   ├── views/
│   │   ├── user/
│   │   │   ├── HomeView.vue     # 用户主页（录音入口）
│   │   │   ├── HistoryView.vue  # 情绪历史
│   │   │   └── ReportView.vue   # 个人分析报告
│   │   │
│   │   └── admin/
│   │       ├── DashboardView.vue
│   │       ├── UsersView.vue
│   │       ├── AlertsView.vue
│   │       └── AnalysisDetailView.vue
│   │
│   ├── components/
│   │   ├── common/
│   │   │   ├── AppLayout.vue
│   │   │   └── NavBar.vue
│   │   ├── user/
│   │   │   ├── VoiceRecorder.vue    # 核心录音组件
│   │   │   ├── EmotionChart.vue     # 情绪趋势图
│   │   │   └── DepressionGauge.vue  # 抑郁倾向仪表盘
│   │   └── admin/
│   │       ├── UserTable.vue
│   │       ├── StatsCard.vue
│   │       └── AlertBadge.vue
│   │
│   ├── types/                   # TypeScript 类型定义
│   └── utils/
│       └── audioRecorder.ts     # Web Audio API 封装
│
├── public/
├── vite.config.ts
├── tsconfig.json
└── package.json
```

---

## 4. 数据库设计（SQLite）

### 4.1 users 表

```sql
CREATE TABLE users (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    username    VARCHAR(50)  UNIQUE NOT NULL,
    hashed_password VARCHAR(255) NOT NULL,
    role        VARCHAR(10)  NOT NULL DEFAULT 'user',  -- 'user' | 'admin'
    gender      VARCHAR(10),
    age         INTEGER,
    phone       VARCHAR(20),
    is_active   BOOLEAN      DEFAULT TRUE,
    created_at  DATETIME     DEFAULT CURRENT_TIMESTAMP,
    updated_at  DATETIME     DEFAULT CURRENT_TIMESTAMP
);
```

### 4.2 audio_records 表

```sql
CREATE TABLE audio_records (
    id           INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id      INTEGER NOT NULL REFERENCES users(id),
    file_path    VARCHAR(255) NOT NULL,          -- 服务器存储路径
    file_size    INTEGER,                         -- bytes
    duration     FLOAT,                           -- 秒
    mime_type    VARCHAR(50) DEFAULT 'audio/mp3',
    transcription TEXT,                           -- Whisper 转录结果
    status       VARCHAR(20) DEFAULT 'pending',   -- pending|processing|done|failed
    created_at   DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.3 emotion_analyses 表

```sql
CREATE TABLE emotion_analyses (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    record_id       INTEGER NOT NULL REFERENCES audio_records(id),
    user_id         INTEGER NOT NULL REFERENCES users(id),

    -- 情绪分类（主情绪标签）
    primary_emotion VARCHAR(30),   -- joy|sadness|anger|fear|disgust|neutral
    emotion_scores  TEXT,          -- JSON: {"joy":0.1,"sadness":0.8,...}

    -- 抑郁倾向
    depression_level VARCHAR(20),  -- none|mild|moderate|severe
    phq_score        INTEGER,      -- 0-27 PHQ-9 等效评分
    risk_factors     TEXT,         -- JSON: ["sleep_issues","hopelessness",...]

    -- LLM 分析原文
    llm_analysis     TEXT,
    suggestions      TEXT,         -- JSON: ["建议1","建议2"]

    -- 语音特征（可选，如接入声学分析）
    speech_rate      FLOAT,        -- 语速 (words/min)
    voice_energy     FLOAT,        -- 音量能量
    pause_ratio      FLOAT,        -- 停顿比例

    created_at       DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.4 alerts 表

```sql
CREATE TABLE alerts (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id     INTEGER NOT NULL REFERENCES users(id),
    analysis_id INTEGER REFERENCES emotion_analyses(id),
    level       VARCHAR(20) NOT NULL,   -- warning | urgent | critical
    message     TEXT,
    is_read     BOOLEAN DEFAULT FALSE,
    read_by     INTEGER REFERENCES users(id),  -- admin user id
    created_at  DATETIME DEFAULT CURRENT_TIMESTAMP
);
```

### 4.5 SQLAlchemy ORM 示例（user.py）

```python
from sqlalchemy import Column, Integer, String, Boolean, DateTime
from sqlalchemy.sql import func
from app.database import Base

class User(Base):
    __tablename__ = "users"

    id              = Column(Integer, primary_key=True, index=True)
    username        = Column(String(50), unique=True, nullable=False)
    email           = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    role            = Column(String(10), default="user")
    gender          = Column(String(10), nullable=True)
    age             = Column(Integer, nullable=True)
    phone           = Column(String(20), nullable=True)
    is_active       = Column(Boolean, default=True)
    created_at      = Column(DateTime(timezone=True), server_default=func.now())
    updated_at      = Column(DateTime(timezone=True), onupdate=func.now())
```

---

## 5. 后端开发（FastAPI）

### 5.1 项目入口 main.py

```python
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles
from app.routers import auth, user, analysis, admin
from app.database import engine, Base

Base.metadata.create_all(bind=engine)

app = FastAPI(title="语音情绪分析系统", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173"],  # Vue dev server
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/uploads", StaticFiles(directory="uploads"), name="uploads")

app.include_router(auth.router,     prefix="/api/auth",     tags=["认证"])
app.include_router(user.router,     prefix="/api/user",     tags=["用户端"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["分析"])
app.include_router(admin.router,    prefix="/api/admin",    tags=["管理端"])
```

### 5.2 配置管理 config.py

```python
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    DATABASE_URL: str = "sqlite:///./emotion_app.db"
    SECRET_KEY: str = "your-secret-key-change-in-prod"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24h
    UPLOAD_DIR: str = "uploads/audio"
    MAX_AUDIO_SIZE_MB: int = 50

    # LLM 配置
    LLM_PROVIDER: str = "ollama"          # ollama | openai
    OLLAMA_BASE_URL: str = "http://localhost:11434"
    OLLAMA_MODEL: str = "qwen3:8b"
    OPENAI_API_KEY: str = ""

    # Whisper 配置
    WHISPER_PROVIDER: str = "local"       # local | openai
    WHISPER_MODEL: str = "base"           # tiny/base/small/medium

    class Config:
        env_file = ".env"

settings = Settings()
```

### 5.3 数据库连接 database.py

```python
from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker
from app.config import settings

engine = create_engine(
    settings.DATABASE_URL,
    connect_args={"check_same_thread": False}  # SQLite 专用
)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

### 5.4 Whisper 语音转录服务

```python
# services/whisper_service.py
import whisper
import os
from app.config import settings

_model = None

def get_whisper_model():
    global _model
    if _model is None:
        _model = whisper.load_model(settings.WHISPER_MODEL)
    return _model

async def transcribe_audio(file_path: str) -> dict:
    """
    返回: {
        "text": "转录文字",
        "language": "zh",
        "segments": [...]
    }
    """
    if settings.WHISPER_PROVIDER == "openai":
        import openai
        with open(file_path, "rb") as f:
            result = openai.audio.transcriptions.create(
                model="whisper-1", file=f, language="zh"
            )
        return {"text": result.text, "language": "zh", "segments": []}
    else:
        model = get_whisper_model()
        result = model.transcribe(file_path, language="zh")
        return {
            "text": result["text"],
            "language": result.get("language", "zh"),
            "segments": result.get("segments", [])
        }
```

### 5.5 LLM 情绪分析服务

```python
# services/llm_service.py
import httpx, json
from app.config import settings

EMOTION_PROMPT = """
你是一名专业的心理咨询AI助手。请对以下用户语音转录文字进行分析。

转录文字：
{transcription}

请以JSON格式返回分析结果，不要包含任何其他文字：
{{
  "primary_emotion": "joy|sadness|anger|fear|disgust|neutral 中的一个",
  "emotion_scores": {{
    "joy": 0.0, "sadness": 0.0, "anger": 0.0,
    "fear": 0.0, "disgust": 0.0, "neutral": 0.0
  }},
  "depression_level": "none|mild|moderate|severe 中的一个",
  "phq_score": 0,
  "risk_factors": ["列出检测到的风险因素"],
  "llm_analysis": "详细的分析说明（中文，100-200字）",
  "suggestions": ["具体的改善建议1", "具体的改善建议2", "具体的改善建议3"]
}}
"""

async def analyze_emotion(transcription: str) -> dict:
    prompt = EMOTION_PROMPT.format(transcription=transcription)

    if settings.LLM_PROVIDER == "ollama":
        async with httpx.AsyncClient(timeout=120.0) as client:
            resp = await client.post(
                f"{settings.OLLAMA_BASE_URL}/api/generate",
                json={
                    "model": settings.OLLAMA_MODEL,
                    "prompt": prompt,
                    "stream": False,
                    "format": "json"
                }
            )
            resp.raise_for_status()
            raw = resp.json()["response"]
    else:
        import openai
        completion = openai.chat.completions.create(
            model="gpt-4o-mini",
            messages=[{"role": "user", "content": prompt}],
            response_format={"type": "json_object"}
        )
        raw = completion.choices[0].message.content

    return json.loads(raw)
```

### 5.6 核心分析流程 analysis_service.py

```python
# services/analysis_service.py
import uuid, os, shutil
from fastapi import UploadFile, HTTPException
from sqlalchemy.orm import Session
from app.config import settings
from app.models.audio_record import AudioRecord
from app.models.emotion_analyses import EmotionAnalysis
from app.models.alert import Alert
from app.services.whisper_service import transcribe_audio
from app.services.llm_service import analyze_emotion
import json

async def process_voice_analysis(
    file: UploadFile,
    user_id: int,
    db: Session
) -> dict:
    # 1. 保存音频文件
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    ext = file.filename.split(".")[-1] if "." in file.filename else "webm"
    filename = f"{user_id}_{uuid.uuid4().hex}.{ext}"
    file_path = os.path.join(settings.UPLOAD_DIR, filename)

    with open(file_path, "wb") as f:
        shutil.copyfileobj(file.file, f)

    file_size = os.path.getsize(file_path)

    # 2. 创建 audio_record
    record = AudioRecord(
        user_id=user_id,
        file_path=file_path,
        file_size=file_size,
        status="processing"
    )
    db.add(record)
    db.commit()
    db.refresh(record)

    try:
        # 3. Whisper 转录
        transcription_result = await transcribe_audio(file_path)
        transcription_text = transcription_result["text"]

        record.transcription = transcription_text
        record.status = "done"
        db.commit()

        # 4. LLM 情绪分析
        analysis_data = await analyze_emotion(transcription_text)

        # 5. 存储分析结果
        analysis = EmotionAnalysis(
            record_id=record.id,
            user_id=user_id,
            primary_emotion=analysis_data.get("primary_emotion"),
            emotion_scores=json.dumps(analysis_data.get("emotion_scores", {})),
            depression_level=analysis_data.get("depression_level"),
            phq_score=analysis_data.get("phq_score", 0),
            risk_factors=json.dumps(analysis_data.get("risk_factors", [])),
            llm_analysis=analysis_data.get("llm_analysis"),
            suggestions=json.dumps(analysis_data.get("suggestions", []))
        )
        db.add(analysis)
        db.commit()
        db.refresh(analysis)

        # 6. 抑郁风险预警
        await _check_and_create_alert(analysis, user_id, db)

        return {"record_id": record.id, "analysis_id": analysis.id, **analysis_data}

    except Exception as e:
        record.status = "failed"
        db.commit()
        raise HTTPException(status_code=500, detail=f"分析失败: {str(e)}")


async def _check_and_create_alert(analysis, user_id: int, db: Session):
    level_map = {
        "moderate": ("warning",  "检测到中度抑郁倾向，建议关注。"),
        "severe":   ("critical", "检测到重度抑郁倾向，需要立即关注！"),
    }
    if analysis.depression_level in level_map:
        level, message = level_map[analysis.depression_level]
        alert = Alert(
            user_id=user_id,
            analysis_id=analysis.id,
            level=level,
            message=message
        )
        db.add(alert)
        db.commit()
```

### 5.7 路由示例 routers/analysis.py

```python
from fastapi import APIRouter, Depends, UploadFile, File, HTTPException
from sqlalchemy.orm import Session
from app.database import get_db
from app.dependencies import get_current_user
from app.services.analysis_service import process_voice_analysis
from app.models.emotion_analyses import EmotionAnalysis
from app.schemas.analysis import AnalysisResponse, AnalysisListItem

router = APIRouter()

@router.post("/upload", response_model=AnalysisResponse)
async def upload_audio(
    file: UploadFile = File(...),
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """上传语音文件并触发分析"""
    allowed = ["audio/webm", "audio/mp4", "audio/wav", "audio/mpeg", "audio/ogg"]
    if file.content_type not in allowed:
        raise HTTPException(400, "不支持的音频格式")
    return await process_voice_analysis(file, current_user.id, db)


@router.get("/history", response_model=list[AnalysisListItem])
def get_history(
    skip: int = 0,
    limit: int = 20,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """获取当前用户的情绪分析历史"""
    return db.query(EmotionAnalysis)\
             .filter(EmotionAnalysis.user_id == current_user.id)\
             .order_by(EmotionAnalysis.created_at.desc())\
             .offset(skip).limit(limit).all()


@router.get("/{analysis_id}", response_model=AnalysisResponse)
def get_analysis_detail(
    analysis_id: int,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    analysis = db.query(EmotionAnalysis)\
                 .filter(EmotionAnalysis.id == analysis_id,
                         EmotionAnalysis.user_id == current_user.id)\
                 .first()
    if not analysis:
        raise HTTPException(404, "记录不存在")
    return analysis
```

---

## 6. 前端开发（Vue 3）

### 6.1 核心依赖 package.json

```json
{
  "dependencies": {
    "vue": "^3.4.0",
    "vue-router": "^4.3.0",
    "pinia": "^2.1.0",
    "axios": "^1.6.0",
    "element-plus": "^2.6.0",
    "echarts": "^5.4.0",
    "vue-echarts": "^6.6.0",
    "@vueuse/core": "^10.9.0"
  },
  "devDependencies": {
    "typescript": "^5.4.0",
    "@vitejs/plugin-vue": "^5.0.0",
    "vite": "^5.2.0"
  }
}
```

### 6.2 路由配置 router/index.ts

```typescript
import { createRouter, createWebHistory } from 'vue-router'
import { useAuthStore } from '@/stores/auth'

const router = createRouter({
  history: createWebHistory(),
  routes: [
    { path: '/login',  component: () => import('@/views/LoginView.vue') },
    { path: '/register', component: () => import('@/views/RegisterView.vue') },

    // 用户端（需登录）
    {
      path: '/user',
      component: () => import('@/components/common/UserLayout.vue'),
      meta: { requiresAuth: true, role: 'user' },
      children: [
        { path: '',        component: () => import('@/views/user/HomeView.vue') },
        { path: 'history', component: () => import('@/views/user/HistoryView.vue') },
        { path: 'report',  component: () => import('@/views/user/ReportView.vue') },
      ]
    },

    // Admin端（需admin权限）
    {
      path: '/admin',
      component: () => import('@/components/common/AdminLayout.vue'),
      meta: { requiresAuth: true, role: 'admin' },
      children: [
        { path: '',        component: () => import('@/views/admin/DashboardView.vue') },
        { path: 'users',   component: () => import('@/views/admin/UsersView.vue') },
        { path: 'alerts',  component: () => import('@/views/admin/AlertsView.vue') },
        { path: 'analysis/:id', component: () => import('@/views/admin/AnalysisDetailView.vue') },
      ]
    },

    { path: '/', redirect: '/user' },
    { path: '/:pathMatch(.*)*', redirect: '/login' }
  ]
})

router.beforeEach((to, from, next) => {
  const auth = useAuthStore()
  if (to.meta.requiresAuth && !auth.isLoggedIn) {
    return next('/login')
  }
  if (to.meta.role === 'admin' && auth.user?.role !== 'admin') {
    return next('/user')
  }
  next()
})

export default router
```

### 6.3 Pinia Auth Store

```typescript
// stores/auth.ts
import { defineStore } from 'pinia'
import { ref, computed } from 'vue'
import { authApi } from '@/api/auth'

export const useAuthStore = defineStore('auth', () => {
  const token = ref<string | null>(localStorage.getItem('token'))
  const user  = ref<User | null>(JSON.parse(localStorage.getItem('user') || 'null'))

  const isLoggedIn = computed(() => !!token.value)

  async function login(username: string, password: string) {
    const res = await authApi.login({ username, password })
    token.value = res.access_token
    user.value  = res.user
    localStorage.setItem('token', res.access_token)
    localStorage.setItem('user', JSON.stringify(res.user))
  }

  function logout() {
    token.value = null
    user.value  = null
    localStorage.removeItem('token')
    localStorage.removeItem('user')
  }

  return { token, user, isLoggedIn, login, logout }
})
```

### 6.4 Axios 封装 api/request.ts

```typescript
import axios from 'axios'
import { useAuthStore } from '@/stores/auth'
import router from '@/router'

const request = axios.create({
  baseURL: import.meta.env.VITE_API_BASE_URL || 'http://localhost:8000/api',
  timeout: 60000,  // 音频上传需要较长超时
})

request.interceptors.request.use(config => {
  const auth = useAuthStore()
  if (auth.token) {
    config.headers.Authorization = `Bearer ${auth.token}`
  }
  return config
})

request.interceptors.response.use(
  res => res.data,
  err => {
    if (err.response?.status === 401) {
      const auth = useAuthStore()
      auth.logout()
      router.push('/login')
    }
    return Promise.reject(err.response?.data || err)
  }
)

export default request
```

### 6.5 核心组件：语音录制 VoiceRecorder.vue

```vue
<template>
  <div class="voice-recorder">
    <div class="recorder-status">{{ statusText }}</div>

    <el-button
      :type="isRecording ? 'danger' : 'primary'"
      :icon="isRecording ? StopFilled : Microphone"
      circle size="large"
      @click="toggleRecording"
      :loading="isUploading"
    />

    <div v-if="audioBlob" class="preview">
      <audio :src="audioUrl" controls />
      <el-button @click="submitAudio" :loading="isUploading">
        提交分析
      </el-button>
    </div>

    <div v-if="analysisResult" class="result">
      <EmotionResult :data="analysisResult" />
    </div>
  </div>
</template>

<script setup lang="ts">
import { ref, computed } from 'vue'
import { Microphone, StopFilled } from '@element-plus/icons-vue'
import { ElMessage } from 'element-plus'
import { analysisApi } from '@/api/analysis'

const isRecording  = ref(false)
const isUploading  = ref(false)
const audioBlob    = ref<Blob | null>(null)
const audioUrl     = ref('')
const analysisResult = ref(null)

let mediaRecorder: MediaRecorder | null = null
let chunks: BlobPart[] = []

const statusText = computed(() => {
  if (isUploading.value) return '分析中，请稍候...'
  if (isRecording.value) return '录音中，点击停止'
  if (audioBlob.value)   return '录音完成，可提交分析'
  return '点击开始录音'
})

async function toggleRecording() {
  if (isRecording.value) {
    mediaRecorder?.stop()
    isRecording.value = false
    return
  }
  try {
    const stream = await navigator.mediaDevices.getUserMedia({ audio: true })
    chunks = []
    mediaRecorder = new MediaRecorder(stream, { mimeType: 'audio/webm' })
    mediaRecorder.ondataavailable = e => chunks.push(e.data)
    mediaRecorder.onstop = () => {
      audioBlob.value = new Blob(chunks, { type: 'audio/webm' })
      audioUrl.value  = URL.createObjectURL(audioBlob.value)
      stream.getTracks().forEach(t => t.stop())
    }
    mediaRecorder.start()
    isRecording.value = true
  } catch {
    ElMessage.error('无法访问麦克风，请检查浏览器权限')
  }
}

async function submitAudio() {
  if (!audioBlob.value) return
  isUploading.value = true
  try {
    const form = new FormData()
    form.append('file', audioBlob.value, 'recording.webm')
    const result = await analysisApi.uploadAudio(form)
    analysisResult.value = result
    ElMessage.success('分析完成')
  } catch (e: any) {
    ElMessage.error(e.detail || '分析失败，请重试')
  } finally {
    isUploading.value = false
  }
}
</script>
```

---

## 7. 语音处理与AI分析模块

### 7.1 分析 Pipeline 流程图

```
用户录音 (WebM/WAV)
       │
       ▼
  音频文件保存
  /uploads/audio/
       │
       ▼
 Whisper 语音转录
  → 中文文字输出
       │
       ▼
 LLM 情绪分析 (Qwen3:8B / GPT-4o-mini)
  Prompt 包含：
  - 情绪识别（6维）
  - 抑郁倾向评估
  - PHQ-9 等效评分
  - 风险因素提取
  - 改善建议生成
       │
       ├── PHQ分数 ≥ 10 → 触发预警 → alerts 表
       │
       ▼
  结果存入 emotion_analyses 表
       │
       ▼
  返回结果给前端展示
```

### 7.2 PHQ-9 评分映射

| PHQ 分数 | 抑郁等级 | depression_level | 预警级别 |
|----------|----------|-----------------|---------|
| 0–4      | 无抑郁   | none            | 无      |
| 5–9      | 轻度     | mild            | 无      |
| 10–14    | 中度     | moderate        | warning |
| 15–19    | 中重度   | moderate-severe | warning |
| 20–27    | 重度     | severe          | critical |

### 7.3 音频格式支持说明

| 格式 | MIME Type | 说明 |
|------|-----------|------|
| WebM | audio/webm | 浏览器 MediaRecorder 默认输出，推荐 |
| WAV  | audio/wav  | 无损，文件较大 |
| MP3  | audio/mpeg | 兼容性好 |
| M4A  | audio/mp4  | iOS Safari |

> Whisper 支持所有主流音频格式，无需额外转码。

---

## 8. API接口文档

### 认证相关

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/auth/register` | 用户注册 |
| POST | `/api/auth/login` | 用户登录（返回JWT）|
| GET  | `/api/auth/me` | 获取当前用户信息 |

### 用户端

| Method | Path | 描述 |
|--------|------|------|
| POST | `/api/analysis/upload` | 上传语音并触发分析 |
| GET  | `/api/analysis/history` | 获取历史分析列表 |
| GET  | `/api/analysis/{id}` | 获取单条分析详情 |
| GET  | `/api/user/profile` | 获取个人信息 |
| PUT  | `/api/user/profile` | 更新个人信息 |

### Admin端

| Method | Path | 描述 |
|--------|------|------|
| GET  | `/api/admin/stats` | 统计数据汇总 |
| GET  | `/api/admin/users` | 用户列表（支持搜索/分页）|
| GET  | `/api/admin/users/{id}/analyses` | 指定用户的分析记录 |
| GET  | `/api/admin/alerts` | 预警列表 |
| PUT  | `/api/admin/alerts/{id}/read` | 标记预警为已读 |
| PUT  | `/api/admin/users/{id}/status` | 启用/停用用户 |

### 接口返回示例

```json
// POST /api/analysis/upload 返回
{
  "record_id": 42,
  "analysis_id": 18,
  "primary_emotion": "sadness",
  "emotion_scores": {
    "joy": 0.05, "sadness": 0.72, "anger": 0.08,
    "fear": 0.10, "disgust": 0.02, "neutral": 0.03
  },
  "depression_level": "moderate",
  "phq_score": 12,
  "risk_factors": ["hopelessness", "sleep_issues", "low_energy"],
  "llm_analysis": "用户表达了明显的无助感和疲惫感，语言中多次出现负面词汇...",
  "suggestions": [
    "建议与心理咨询师进行一次专业评估",
    "保持规律作息，每天保证7-8小时睡眠",
    "尝试轻度有氧运动，如散步或瑜伽"
  ]
}
```

---

## 9. 认证与权限设计

### 9.1 JWT 工具 utils/security.py

```python
from datetime import datetime, timedelta
from jose import JWTError, jwt
from passlib.context import CryptContext
from app.config import settings

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")

def verify_password(plain: str, hashed: str) -> bool:
    return pwd_context.verify(plain, hashed)

def get_password_hash(password: str) -> str:
    return pwd_context.hash(password)

def create_access_token(data: dict) -> str:
    expire = datetime.utcnow() + timedelta(minutes=settings.ACCESS_TOKEN_EXPIRE_MINUTES)
    return jwt.encode({**data, "exp": expire}, settings.SECRET_KEY, algorithm=settings.ALGORITHM)

def decode_token(token: str) -> dict:
    return jwt.decode(token, settings.SECRET_KEY, algorithms=[settings.ALGORITHM])
```

### 9.2 依赖注入 dependencies.py

```python
from fastapi import Depends, HTTPException, status
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.orm import Session
from app.database import get_db
from app.models.user import User
from app.utils.security import decode_token

oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/api/auth/login")

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> User:
    try:
        payload = decode_token(token)
        user_id = payload.get("sub")
    except Exception:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "无效的认证凭证")
    user = db.query(User).filter(User.id == int(user_id)).first()
    if not user or not user.is_active:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "用户不存在或已停用")
    return user

def get_admin_user(current_user: User = Depends(get_current_user)) -> User:
    if current_user.role != "admin":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "需要管理员权限")
    return current_user
```

---

## 10. 部署方案

### 10.1 依赖安装

```bash
# 后端
pip install fastapi uvicorn[standard] sqlalchemy alembic
pip install python-multipart python-jose[cryptography] passlib[bcrypt]
pip install openai-whisper httpx pydantic-settings

# 前端
npm install
```

### 10.2 环境变量 .env

```env
DATABASE_URL=sqlite:///./emotion_app.db
SECRET_KEY=your-super-secret-key-minimum-32-chars
UPLOAD_DIR=uploads/audio

LLM_PROVIDER=ollama
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=qwen3:8b

WHISPER_PROVIDER=local
WHISPER_MODEL=base
```

### 10.3 启动命令

```bash
# 初始化数据库
alembic upgrade head

# 启动后端（开发）
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000

# 启动前端（开发）
npm run dev

# 生产构建
npm run build
# 然后用 nginx 或 uvicorn 的 StaticFiles 托管 dist/
```

### 10.4 Vite 代理配置（开发环境）

```typescript
// vite.config.ts
export default defineConfig({
  plugins: [vue()],
  server: {
    proxy: {
      '/api': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      },
      '/uploads': {
        target: 'http://localhost:8000',
        changeOrigin: true,
      }
    }
  }
})
```

### 10.5 数据库迁移流程

```bash
# 初始化 alembic
alembic init alembic

# 生成迁移脚本（修改模型后）
alembic revision --autogenerate -m "add emotion_analyses table"

# 执行迁移
alembic upgrade head

# 回滚
alembic downgrade -1
```

---

## 附录：开发优先级建议

| 阶段 | 任务 | 预估工时 |
|------|------|---------|
| P0 | 数据库建表 + Auth模块（注册/登录/JWT）| 1天 |
| P0 | 语音上传接口 + Whisper转录 | 1天 |
| P0 | LLM情绪分析 + 结果存储 | 1天 |
| P1 | 用户端前端（录音组件 + 历史记录）| 2天 |
| P1 | Admin端前端（大盘 + 用户管理）| 2天 |
| P2 | 预警系统 + 情绪趋势图表 | 1天 |
| P2 | 个人分析报告生成 | 1天 |

> **建议开发顺序**：后端API → Postman验证 → 前端对接 → 联调测试
