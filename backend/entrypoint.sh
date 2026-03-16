#!/bin/sh
set -e

# 修正 Docker volume 挂载目录的权限（volume 首次创建时 owner 为 root）
mkdir -p /app/data /app/data/hf_cache /app/data/cache /app/uploads/audio
chown -R appuser:appgroup /app/data /app/uploads/audio

# 降权到 appuser 后启动 uvicorn
exec gosu appuser uvicorn main:app --host 0.0.0.0 --port 8000 --workers 1