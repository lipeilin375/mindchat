import json
import logging
import httpx
from pathlib import Path
from app.config import settings

from app.services.emotion_service import EmotionInference

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名专业的心理咨询AI助手，具备情绪识别和抑郁风险评估能力。
请严格按照JSON格式输出，不要包含任何额外说明或markdown标记。"""

ANALYSIS_PROMPT = """请对以下用户语音转录文字进行专业的情绪与心理状态分析。

【转录文字】
{transcription}

【情绪预测】
{emotion_scores_json}

请返回以下JSON格式的分析结果（所有字段必填）：
{{
  "depression_level": "<从 none/mild/moderate/severe 中选一个>",
  "phq_score": <0-27的整数，基于PHQ-9量表估算>,
  "risk_factors": ["<风险因素1>", "<风险因素2>"],
  "llm_analysis": "<详细分析说明，100-200字中文>",
  "suggestions": ["<改善建议1>", "<改善建议2>", "<改善建议3>"]
}}

评分标准：
- PHQ 0-4: none（无抑郁）
- PHQ 5-9: mild（轻度）
- PHQ 10-14: moderate（中度）
- PHQ 15-27: severe（重度）
"""


# ─────────────────────────────────────────────────────────────────────────────
# Helpers
# ─────────────────────────────────────────────────────────────────────────────

def _parse_llm_json(raw: str) -> dict:
    """Parse JSON from LLM output, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def _extract_ollama_response(body: str) -> str:
    """
    Ollama /api/generate returns either a single JSON object or NDJSON.
    Iterate all lines and return the `response` field of the last valid object.
    """
    last_response = "{}"
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            if "response" in obj:
                last_response = obj["response"]
        except json.JSONDecodeError:
            continue
    return last_response


def _extract_openrouter_content(data: dict) -> str:
    """
    Parse OpenRouter / OpenAI-compatible chat completion response.

    Response shape:
    {
      "choices": [
        {
          "message": { "content": "<json string>" },
          ...
        }
      ],
      ...
    }
    Also handles cases where the model wraps content inside a reasoning block
    (e.g. some models return `reasoning` + `content` separately).
    """
    choices = data.get("choices") or []
    if not choices:
        raise ValueError("LLM 响应中 choices 为空")

    message = choices[0].get("message") or {}

    # Some providers put the actual answer in `content`, others in `reasoning`
    content = message.get("content") or message.get("reasoning") or ""
    if not content:
        raise ValueError("LLM 响应 message.content 为空")

    return content


# ─────────────────────────────────────────────────────────────────────────────
# Public entry point
# ─────────────────────────────────────────────────────────────────────────────

async def analyze_emotion(audio_path, transcription: str) -> dict:
    BASE_DIR = Path(__file__).resolve().parent.parent.parent
    ckpt_path = "/app/app/assets/tune_emotion.pt"
    # ckpt_path = BASE_DIR / "assets" / "tune_emotion.pt"
    infer = EmotionInference(ckpt_path)
    result = infer.predict(audio_path=audio_path, text=transcription)
    return result


async def analyze_mental_data(transcription: str, emotion_scores_json: str) -> dict:
    provider = settings.LLM_PROVIDER.lower()
    if provider == "ollama":
        return await _call_ollama(transcription, emotion_scores_json)
    elif provider == "custom":
        return await _call_custom(transcription, emotion_scores_json)
    elif provider == "openai":
        return await _call_openai(transcription, emotion_scores_json)
    else:
        raise ValueError(f"Unsupported LLM_PROVIDER: {settings.LLM_PROVIDER}")


# ─────────────────────────────────────────────────────────────────────────────
# Provider implementations
# ─────────────────────────────────────────────────────────────────────────────

async def _call_ollama(transcription: str, emotion_scores_json: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(transcription=transcription, emotion_scores_json=emotion_scores_json)
    payload = {
        "model": settings.OLLAMA_MODEL,
        "prompt": prompt,
        "system": SYSTEM_PROMPT,
        "stream": False,
        "format": "json",
        "options": {
            "temperature": 0.3,
            "num_predict": 1024,
        },
    }
    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(
            f"{settings.OLLAMA_BASE_URL}/api/generate",
            json=payload,
        )
        resp.raise_for_status()
        raw = _extract_ollama_response(resp.text)

    logger.debug(f"Ollama raw excerpt: {raw[:300]}")
    try:
        return _parse_llm_json(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Ollama JSON parse error: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"LLM 返回格式错误: {e}")


async def _call_custom(transcription: str, emotion_scores_json: str) -> dict:
    """
    Call any OpenAI-compatible API (OpenRouter, custom endpoint, etc.).
    Configured via:
        CUSTOM_LLM_BASE_URL  — e.g. https://openrouter.ai/api/v1
        CUSTOM_LLM_MODEL     — e.g. anthropic/claude-3-haiku
        CUSTOM_LLM_API_KEY   — Bearer token
    """
    if not settings.CUSTOM_LLM_API_KEY:
        raise ValueError("CUSTOM_LLM_API_KEY 未配置，无法使用 custom LLM provider")

    prompt  = ANALYSIS_PROMPT.format(transcription=transcription, emotion_scores_json=emotion_scores_json)
    url     = f"{settings.CUSTOM_LLM_BASE_URL.rstrip('/')}"
    headers = {
        "Authorization": f"Bearer {settings.CUSTOM_LLM_API_KEY}",
        "Content-Type":  "application/json",
        # OpenRouter requires these for tracking; harmless on other providers
        "HTTP-Referer":  "https://emotion-analysis-app",
        "X-Title":       "EmotionAnalysisApp",
    }
    payload = {
        "model": settings.CUSTOM_LLM_MODEL,
        "messages": [
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        "temperature": 0.3,
        "max_tokens":  1024,
        "response_format": {"type": "json_object"},
    }

    logger.info(f"Custom LLM call → {url} model={settings.CUSTOM_LLM_MODEL}")

    async with httpx.AsyncClient(timeout=180.0) as client:
        resp = await client.post(url, headers=headers, json=payload)
        resp.raise_for_status()
        data = resp.json()

    logger.debug(f"Custom LLM raw response: {json.dumps(data)[:400]}")

    try:
        raw = _extract_openrouter_content(data)
        return _parse_llm_json(raw)
    except (json.JSONDecodeError, ValueError) as e:
        logger.error(f"Custom LLM parse error: {e}\nData: {str(data)[:500]}")
        raise ValueError(f"LLM 返回格式错误: {e}")


async def _call_openai(transcription: str, emotion_scores_json: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(transcription=transcription, emotion_scores_json=emotion_scores_json)
    import openai
    client = openai.AsyncOpenAI(api_key=settings.OPENAI_API_KEY)
    completion = await client.chat.completions.create(
        model="gpt-4o-mini",
        messages=[
            {"role": "system", "content": SYSTEM_PROMPT},
            {"role": "user",   "content": prompt},
        ],
        response_format={"type": "json_object"},
        temperature=0.3,
        max_tokens=1024,
    )
    raw = completion.choices[0].message.content or "{}"
    try:
        return _parse_llm_json(raw)
    except json.JSONDecodeError as e:
        logger.error(f"OpenAI JSON parse error: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"LLM 返回格式错误: {e}")