import logging
import os
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.config import settings
from app.database import engine, Base

# Import all models so SQLAlchemy registers them before create_all
import app.models  # noqa: F401

from app.routers import auth, user, analysis, admin
from app.database import SessionLocal
from app.utils.init_db import create_default_admin

logging.basicConfig(
    level=logging.DEBUG if settings.DEBUG else logging.INFO,
    format="%(asctime)s | %(levelname)-8s | %(name)s | %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    # ── Startup ───────────────────────────────────────────────────────────
    logger.info("Starting up — creating database tables if needed...")
    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    Base.metadata.create_all(bind=engine)
    logger.info("Database ready.")
    db = SessionLocal()
    try:
        create_default_admin(db)
    finally:
        db.close()
    yield
    # ── Shutdown ──────────────────────────────────────────────────────────
    logger.info("Shutting down.")


app = FastAPI(
    title=settings.APP_TITLE,
    version=settings.APP_VERSION,
    docs_url="/docs",
    redoc_url="/redoc",
    lifespan=lifespan,
)

# ── CORS ──────────────────────────────────────────────────────────────────────
app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.CORS_ORIGINS,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Static file serving for uploaded audio ────────────────────────────────────
os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
app.mount("/uploads", StaticFiles(directory=os.path.dirname(settings.UPLOAD_DIR)), name="uploads")

# ── Routers ───────────────────────────────────────────────────────────────────
app.include_router(auth.router,     prefix="/api/auth",     tags=["认证"])
app.include_router(user.router,     prefix="/api/user",     tags=["用户端"])
app.include_router(analysis.router, prefix="/api/analysis", tags=["分析"])
app.include_router(admin.router,    prefix="/api/admin",    tags=["管理端"])


@app.get("/health", tags=["健康检查"])
def health_check():
    return {"status": "ok", "version": settings.APP_VERSION}