import json
import logging
import httpx
from app.config import settings

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """你是一名专业的心理咨询AI助手，具备情绪识别和抑郁风险评估能力。
请严格按照JSON格式输出，不要包含任何额外说明或markdown标记。"""

ANALYSIS_PROMPT = """请对以下用户语音转录文字进行专业的情绪与心理状态分析。

【转录文字】
{transcription}

请返回以下JSON格式的分析结果（所有字段必填）：
{{
  "primary_emotion": "<从 joy/sadness/anger/fear/disgust/neutral 中选一个>",
  "emotion_scores": {{
    "joy": <0.0-1.0>,
    "sadness": <0.0-1.0>,
    "anger": <0.0-1.0>,
    "fear": <0.0-1.0>,
    "disgust": <0.0-1.0>,
    "neutral": <0.0-1.0>
  }},
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


def _parse_llm_json(raw: str) -> dict:
    """Robustly parse JSON from LLM output, stripping markdown fences if present."""
    text = raw.strip()
    if text.startswith("```"):
        lines = text.split("\n")
        text = "\n".join(lines[1:-1] if lines[-1].strip() == "```" else lines[1:])
    return json.loads(text.strip())


def _extract_ollama_response(body: str) -> str:
    """
    Ollama /api/generate may return either:
      - A single JSON object  (stream=false, recent versions)
      - NDJSON lines          (one JSON object per line, older versions)

    In both cases the final non-empty line contains the completed response.
    We parse each line and return the `response` field from the last valid one.
    """
    last_response = "{}"
    for line in body.splitlines():
        line = line.strip()
        if not line:
            continue
        try:
            obj = json.loads(line)
            # `response` holds the generated text chunk / full text
            if "response" in obj:
                last_response = obj["response"]
        except json.JSONDecodeError:
            continue
    return last_response


async def analyze_emotion(transcription: str) -> dict:
    if settings.LLM_PROVIDER == "ollama":
        return await _call_ollama(transcription)
    return await _call_openai(transcription)


async def _call_ollama(transcription: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(transcription=transcription)
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
        # Use .text to avoid httpx trying to parse multi-line NDJSON as one JSON
        raw = _extract_ollama_response(resp.text)

    logger.debug(f"Ollama raw response excerpt: {raw[:300]}")
    try:
        return _parse_llm_json(raw)
    except json.JSONDecodeError as e:
        logger.error(f"Ollama JSON parse error: {e}\nRaw: {raw[:500]}")
        raise ValueError(f"LLM 返回格式错误: {e}")


async def _call_openai(transcription: str) -> dict:
    prompt = ANALYSIS_PROMPT.format(transcription=transcription)
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