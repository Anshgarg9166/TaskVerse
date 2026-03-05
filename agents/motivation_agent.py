# ─────────────────────────────────────────────
#  Taskverse – Motivation Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from typing import Any, Dict

from database.db import AnalyticsRepository, get_database
from llm.groq_client import chat_completion_json
from llm.prompts import MOTIVATION_SYSTEM, motivation_user
from utils.logger import log

# Fallback messages when LLM is unavailable
_FALLBACK_MESSAGES = [
    "You're doing amazing! Keep pushing forward. 💪",
    "Every task completed is a step closer to your goal. 🚀",
    "Small progress is still progress. Keep going! 🔥",
]

_fallback_index = 0


class MotivationAgent:
    """
    Generates personalised motivational messages based on the user's
    daily analytics using the LLM.
    """

    async def get_motivation(self, telegram_id: int) -> str:
        """
        Fetch today's analytics and generate a motivational message.
        """
        global _fallback_index

        log.info("MotivationAgent.get_motivation – user={}", telegram_id)

        # 1. Collect stats
        db = await get_database()
        analytics = AnalyticsRepository(db)
        today_stats = await analytics.get_today(telegram_id) or {}

        stats: Dict[str, Any] = {
            "tasks_completed": today_stats.get("tasks_completed", 0),
            "habits_completed": today_stats.get("habits_completed", 0),
            "streak": today_stats.get("tasks_completed", 0),  # proxy
        }

        # 2. LLM generation
        try:
            parsed = await chat_completion_json(
                MOTIVATION_SYSTEM,
                motivation_user(stats),
                temperature=0.8,  # more creative
            )
            message = parsed.get("message", "")
            quote = parsed.get("quote", "")

            if not message:
                raise ValueError("Empty message from LLM")

            result = message
            if quote:
                result += f'\n\n_"{quote}"_'
            return result

        except Exception as exc:
            log.warning("MotivationAgent LLM fallback: {}", exc)
            msg = _FALLBACK_MESSAGES[_fallback_index % len(_FALLBACK_MESSAGES)]
            _fallback_index += 1
            return msg
