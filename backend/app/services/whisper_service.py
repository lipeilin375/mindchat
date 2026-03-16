import logging
from app.config import settings

logger = logging.getLogger(__name__)

_whisper_model = None


def _get_local_model():
    """
    Lazy-load a faster-whisper WhisperModel.
    device / compute_type 完全由配置决定，不在代码里做自动检测。
    默认 cpu + int8，若宿主机有 GPU 可在 .env 设置 WHISPER_DEVICE=cuda。
    """
    global _whisper_model
    if _whisper_model is None:
        from faster_whisper import WhisperModel

        device  = settings.WHISPER_DEVICE                              # cpu | cuda
        compute = "float16" if device == "cuda" else "int8"

        logger.info(f"Loading faster-whisper '{settings.WHISPER_MODEL}' | device={device} compute_type={compute}")
        _whisper_model = WhisperModel(
            settings.WHISPER_MODEL,
            device=device,
            compute_type=compute,
        )
        logger.info("faster-whisper model ready.")
    return _whisper_model


async def transcribe_audio(file_path: str) -> dict:
    """
    Returns:
        { "text": str, "language": str, "segments": list[dict] }
    """
    if settings.WHISPER_PROVIDER == "openai":
        import openai
        client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
        with open(file_path, "rb") as f:
            result = await client.audio.transcriptions.create(
                model="whisper-1",
                file=f,
                language="zh",
                response_format="verbose_json",
            )
        return {
            "text":     result.text,
            "language": result.language or "zh",
            "segments": getattr(result, "segments", []) or [],
        }

    # ── faster-whisper 本地推理 ───────────────────────────────────────────────
    model = _get_local_model()
    segments_gen, info = model.transcribe(
        file_path,
        language="zh",
        task="transcribe",
        beam_size=5,
        vad_filter=True,
        vad_parameters={"min_silence_duration_ms": 500},
    )

    segments   = []
    text_parts = []
    for seg in segments_gen:
        text_parts.append(seg.text)
        segments.append({
            "start": round(seg.start, 2),
            "end":   round(seg.end,   2),
            "text":  seg.text,
        })

    return {
        "text":     "".join(text_parts).strip(),
        "language": info.language or "zh",
        "segments": segments,
    }