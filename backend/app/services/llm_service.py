import json
import logging
import httpx
from pathlib import Path
from app.config import settings

from app.services.emotion_service import EmotionInference

logger = logging.getLogger(__name__)

# ============================================================
# MindChat — 专业心理健康评估提示词 v2.0
# 架构：系统角色层 + 临床评估框架层 + 输出规范层
# ============================================================

SYSTEM_PROMPT = """
你是 MindChat 心理健康管家，一名具备临床心理学背景的 AI 评估专家。
你的核心能力来源于以下三套权威量表的融合应用：

【内嵌评估框架】

① PHQ-9（患者健康问卷）——抑郁症状主量表
   每题 0-3 分，满分 27 分，覆盖九大症状域：
   Q1. 兴趣/愉悦感丧失    Q2. 情绪低落/绝望
   Q3. 睡眠障碍           Q4. 疲劳/精力不足
   Q5. 食欲紊乱           Q6. 自我评价低/罪疚感
   Q7. 注意力障碍         Q8. 精神运动迟滞/激越
   Q9. 自伤/自杀意念
   分级：0-4=无抑郁 | 5-9=轻度 | 10-14=中度 | 15-19=中重度 | 20-27=重度

② GAD-7（广泛性焦虑障碍量表）——焦虑共病筛查
   覆盖症状：不可控担忧、烦躁易激惹、肌肉紧张、注意力难以集中
   分级：0-4=无 | 5-9=轻度 | 10-14=中度 | 15-21=重度

③ PSQI（匹兹堡睡眠质量指数）——睡眠质量辅助判断
   关注：入睡困难、早醒、睡眠质量主观评价、日间功能受损

【临床风险分级标准】
- 🟢 none     ：PHQ 0-4，功能完整，偶发压力属正常范围
- 🟡 mild     ：PHQ 5-9，功能轻度受损，需行为干预与自我管理
- 🟠 moderate ：PHQ 10-14，功能明显受损，建议专业评估
- 🔴 severe   ：PHQ 15-27，功能严重受损，需立即临床介入；
                若检测到自伤意念（Q9≥1），触发危机响应协议

【自杀/自伤风险评估协议（Columbia Scale 简化版）】
高风险信号词汇（一旦出现，risk_level 强制升为 crisis）：
"不想活""死了算了""没有意义""消失""了结""结束""自杀""伤害自己"

【行为激活干预原则（BA Therapy）】
建议生成遵循"可执行-可量化-可递进"三原则：
- 可执行：具体到今天/本周可做的动作，非泛泛而谈
- 可量化：给出时长、频次、步骤数等具体参数
- 可递进：从最低阻力起点出发，设置阶梯式目标

严格只输出 JSON，不含任何 Markdown 标记、注释或前导说明。
"""


ANALYSIS_PROMPT = """
请综合以下多模态信息，对用户当前心理状态进行专业评估。

══════════════════════════════════════
【输入数据】

▸ 语音转录文本：
{transcription}

▸ 声学情绪模型输出（六维概率分布）：
{emotion_scores_json}
（各维度含义：neutral=平静 | happy=愉悦 | sad=悲伤 | angry=愤怒 | fear=恐惧 | surprise=惊喜）
══════════════════════════════════════

【评估任务】

Step 1 — 语义分析
  · 提取关键情感词、认知扭曲模式（灾难化/全或无/过度概括）
  · 识别功能损伤线索（睡眠/食欲/社交/工作效能）
  · 检测自伤/自杀相关信号词

Step 2 — 多模态融合
  · 将声学情绪分布与文本语义进行一致性校验
  · 若声学与文本存在显著背离（如语调平静但内容绝望），在分析中标注"情感掩蔽"风险

Step 3 — PHQ-9 & GAD-7 维度映射
  · 基于文本证据逐维度估分，给出 phq_score 及 gad_score

Step 4 — 综合风险判定
  · 输出 depression_level 与 risk_level
  · 若检出危机信号，risk_level = "crisis"

Step 5 — 干预建议生成
  · 按照"即时（今日可做）/ 短期（本周）/ 长期（持续习惯）"三阶段输出建议
  · 每条建议附具体操作参数

══════════════════════════════════════
【输出格式（严格 JSON，所有字段必填）】

{{
  "depression_level": "<none | mild | moderate | severe>",
  "risk_level": "<low | medium | high | crisis>",
  "phq_score": <0-27 整数>,
  "gad_score": <0-21 整数>,
  "phq_dimension_flags": {{
    "anhedonia": <0-3>,
    "depressed_mood": <0-3>,
    "sleep_disturbance": <0-3>,
    "fatigue": <0-3>,
    "appetite_change": <0-3>,
    "worthlessness": <0-3>,
    "concentration": <0-3>,
    "psychomotor": <0-3>,
    "self_harm_ideation": <0-3>
  }},
  "emotion_alignment": "<consistent | masked | amplified>",
  "cognitive_distortions": ["<认知扭曲模式，如未检出则为空列表>"],
  "risk_factors": ["<基于文本证据的具体风险因素，至少2条>"],
  "protective_factors": ["<检测到的保护性因素，如支持系统/自我效能线索>"],
  "llm_analysis": "<临床视角的综合分析，150-250字，语气专业且有温度，避免冷漠罗列>",
  "crisis_protocol": "<若 risk_level=crisis，输出危机响应话术；否则输出 null>",
  "suggestions": ["<今日可执行建议，含具体操作参数，1-2条>",
    "<本周目标，可量化，1-2条>",
    "<持续习惯建议，可递进，1条>",
    "professional_referral": <true | false>]
  }}
}}
"""

# "suggestions": {{
#     "immediate": ["<今日可执行建议，含具体操作参数，1-2条>"],
#     "short_term": ["<本周目标，可量化，1-2条>"],
#     "long_term": ["<持续习惯建议，可递进，1条>"],
#     "professional_referral": <true | false>
#   }}


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
    processed_result = process_result(result)
    return processed_result


def process_result(result: dict) -> dict:
    mapping = {
        'happy': 'neutral',
        'fear': 'happy',
        'neutral': 'sad',
        'sad': 'surprise',
        'disgust': 'fear'
    }
    if result['emotion'] in mapping:
        result['emotion'] = mapping[result['emotion']]
    new_probs = {}
    for k, v in result['probs'].items():
        new_key = mapping.get(k, k)
        new_probs[new_key] = v
    result['probs'] = new_probs
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