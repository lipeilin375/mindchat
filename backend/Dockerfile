# ─────────────────────────────────────────────────────────────────────────────
# Stage 1: Builder — install Python deps into a venv
# ─────────────────────────────────────────────────────────────────────────────
FROM python AS builder

WORKDIR /build

RUN apt-get update && apt-get install -y --no-install-recommends \
        build-essential libssl-dev libffi-dev curl \
    && rm -rf /var/lib/apt/lists/*

RUN python -m venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

RUN pip config set global.index-url https://pypi.tuna.tsinghua.edu.cn/simple

COPY requirements.txt .
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt


# ─────────────────────────────────────────────────────────────────────────────
# Stage 2: Runtime image
# ─────────────────────────────────────────────────────────────────────────────
FROM python AS runtime

# gosu: 安全地从 root 降权到 appuser，用于 entrypoint 修正 volume 权限
RUN apt-get update && apt-get install -y --no-install-recommends \
        ffmpeg curl gosu \
    && rm -rf /var/lib/apt/lists/*

COPY --from=builder /opt/venv /opt/venv
ENV PATH="/opt/venv/bin:$PATH"

WORKDIR /app

RUN mkdir -p /app/data /app/uploads/audio /app/data/hf_cache /app/data/cache /home/appuser

ENV HF_HOME=/app/data/hf_cache
ENV XDG_CACHE_HOME=/app/data/cache

EXPOSE 8000

HEALTHCHECK --interval=120s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--workers", "4"]