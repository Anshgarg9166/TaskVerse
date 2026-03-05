# ─────────────────────────────────────────────
#  Taskverse – Groq LLM Client
# ─────────────────────────────────────────────
from __future__ import annotations

import json
from typing import Any, Dict, Optional

from groq import AsyncGroq
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
)

from backend.config import get_settings
from utils.logger import log

settings = get_settings()

# ── Client Singleton ──────────────────────────────────────────────────────────

_client: Optional[AsyncGroq] = None


def get_groq_client() -> AsyncGroq:
    global _client
    if _client is None:
        _client = AsyncGroq(api_key=settings.groq_api_key)
        log.info("Groq client initialised – model={}", settings.groq_model)
    return _client


# ── Core Chat Completion ──────────────────────────────────────────────────────

@retry(
    retry=retry_if_exception_type(Exception),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=1, max=10),
    reraise=True,
)
async def chat_completion(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.3,
    max_tokens: int = 1024,
) -> str:
    """
    Send a chat completion request to Groq and return the raw text.

    Parameters
    ----------
    system_prompt : str
        The system instruction for the LLM.
    user_message : str
        The user turn content.
    temperature : float
        Sampling temperature (lower = more deterministic).
    max_tokens : int
        Maximum tokens in the response.

    Returns
    -------
    str
        Raw text content from the model.
    """
    client = get_groq_client()

    try:
        response = await client.chat.completions.create(
            model=settings.groq_model,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_message},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        content = response.choices[0].message.content
        log.debug("Groq response received – tokens_used={}", response.usage.total_tokens)
        return content or ""
    except Exception as exc:
        log.error("Groq API error: {}", exc)
        raise


async def chat_completion_json(
    system_prompt: str,
    user_message: str,
    temperature: float = 0.2,
    max_tokens: int = 1024,
) -> Dict[str, Any]:
    """
    Like chat_completion but parses and returns a JSON dict.

    Falls back to an empty dict on parse failure.
    """
    raw = await chat_completion(system_prompt, user_message, temperature, max_tokens)
    raw = raw.strip()

    # Strip markdown code fences if the model adds them
    if raw.startswith("```"):
        raw = raw.split("```")[1]
        if raw.startswith("json"):
            raw = raw[4:]

    try:
        return json.loads(raw)
    except json.JSONDecodeError as exc:
        log.warning("JSON parse failed – raw={!r} err={}", raw[:200], exc)
        return {}
