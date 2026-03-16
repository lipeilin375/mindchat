import os
import uuid
import subprocess
import logging
from fastapi import UploadFile
from app.config import settings

logger = logging.getLogger(__name__)

ALLOWED_MIME_TYPES = {
    "audio/webm", "audio/mp4", "audio/wav", "audio/x-wav", "audio/wave",
    "audio/mpeg", "audio/mp3", "audio/ogg", "audio/flac",
    "audio/x-m4a", "application/octet-stream",
}


def _ext_from_mime(mime: str) -> str:
    mapping = {
        "audio/webm": "webm",
        "audio/mp4":  "mp4",
        "audio/wav":  "wav",
        "audio/x-wav": "wav",
        "audio/wave":  "wav",
        "audio/mpeg": "mp3",
        "audio/mp3":  "mp3",
        "audio/ogg":  "ogg",
        "audio/flac": "flac",
        "audio/x-m4a": "m4a",
    }
    return mapping.get(mime, "bin")


async def save_audio_as_mp3(file: UploadFile, user_id: int) -> dict:
    """
    Save the uploaded audio file, converting it to MP3 via ffmpeg.

    Returns:
        {
            "file_path": str,   # final .mp3 path
            "file_name": str,
            "file_size": int,   # bytes of mp3
            "mime_type": "audio/mpeg"
        }

    Raises:
        ValueError: unsupported mime type or conversion failure
    """
    content_type = (file.content_type or "application/octet-stream").lower()
    if content_type not in ALLOWED_MIME_TYPES:
        raise ValueError(f"不支持的音频格式: {content_type}")

    os.makedirs(settings.UPLOAD_DIR, exist_ok=True)
    uid = uuid.uuid4().hex
    src_ext  = _ext_from_mime(content_type)
    src_name = f"{user_id}_{uid}.{src_ext}"
    mp3_name = f"{user_id}_{uid}.mp3"
    src_path = os.path.join(settings.UPLOAD_DIR, src_name)
    mp3_path = os.path.join(settings.UPLOAD_DIR, mp3_name)

    # Write raw upload to disk
    with open(src_path, "wb") as f:
        content = await file.read()
        f.write(content)

    # Convert to mp3 with ffmpeg
    if src_ext == "mp3" and content_type == "audio/mpeg":
        # Already mp3 — just rename
        os.rename(src_path, mp3_path)
    else:
        try:
            result = subprocess.run(
                [
                    "ffmpeg", "-y",
                    "-i", src_path,
                    "-vn",
                    "-ar", "16000",   # 16kHz — optimal for Whisper
                    "-ac", "1",       # mono
                    "-b:a", "64k",    # 64kbps — good balance for speech
                    mp3_path,
                ],
                capture_output=True, timeout=120
            )
            if result.returncode != 0:
                raise RuntimeError(result.stderr.decode())
        except Exception as e:
            logger.error(f"ffmpeg conversion failed: {e}")
            raise ValueError(f"音频转换失败: {e}")
        finally:
            # Remove original upload regardless of success
            if os.path.exists(src_path):
                os.remove(src_path)

    file_size = os.path.getsize(mp3_path)
    return {
        "file_path": mp3_path,
        "file_name": mp3_name,
        "file_size": file_size,
        "mime_type": "audio/mpeg",
    }