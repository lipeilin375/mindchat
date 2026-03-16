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
COPY . .

RUN mkdir -p /app/data /app/uploads/audio /app/data/hf_cache /app/data/cache /home/appuser && \
    addgroup --system appgroup && \
    adduser --system --ingroup appgroup --home /home/appuser appuser && \
    chown -R appuser:appgroup /app /home/appuser && \
    chmod +x /app/entrypoint.sh

ENV HF_HOME=/app/data/hf_cache
ENV XDG_CACHE_HOME=/app/data/cache

# 以 root 启动，entrypoint.sh 修正 volume 权限后用 gosu 切换到 appuser
USER root

EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD curl -f http://localhost:8000/health || exit 1

ENTRYPOINT ["/app/entrypoint.sh"]