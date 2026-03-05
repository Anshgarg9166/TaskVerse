# ─────────────────────────────────────────────
#  Taskverse – Study Planner Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from typing import Any, Dict, List

from database.db import StudyPlanRepository, get_database
from llm.groq_client import chat_completion_json
from llm.prompts import STUDY_PLAN_SYSTEM, study_plan_user
from utils.logger import log


class StudyAgent:
    """
    Generates personalised study plans using the LLM
    and persists them to MongoDB.
    """

    async def create_study_plan(
        self, telegram_id: int, topics_text: str
    ) -> Dict[str, Any]:
        """
        Pipeline: LLM plan generation → DB insert.

        Returns the saved study-plan document.
        """
        log.info(
            "StudyAgent.create_study_plan – user={} topics={!r}",
            telegram_id,
            topics_text,
        )

        # 1. LLM generation
        parsed = await chat_completion_json(
            STUDY_PLAN_SYSTEM,
            study_plan_user(topics_text),
        )

        if not parsed or "blocks" not in parsed:
            log.warning("StudyAgent: LLM fallback for topics={!r}", topics_text)
            parsed = {
                "exam_or_goal": topics_text,
                "blocks": [{"topic": topics_text, "duration_minutes": 45}],
                "total_minutes": 45,
                "tip": "Use the Pomodoro technique for best results.",
            }

        # 2. Build document
        plan_doc: Dict[str, Any] = {
            "telegram_id": telegram_id,
            "exam_or_goal": parsed.get("exam_or_goal", topics_text),
            "blocks": parsed.get("blocks", []),
            "total_minutes": parsed.get("total_minutes", 0),
            "tip": parsed.get("tip", ""),
        }

        # 3. Persist
        db = await get_database()
        repo = StudyPlanRepository(db)
        plan_id = await repo.create(plan_doc)
        plan_doc["_id"] = plan_id

        log.info("StudyAgent: plan created – id={}", plan_id)
        return plan_doc

    async def list_plans(self, telegram_id: int) -> List[Dict[str, Any]]:
        db = await get_database()
        repo = StudyPlanRepository(db)
        return await repo.list_by_user(telegram_id)

    def format_plan_message(self, plan: Dict[str, Any]) -> str:
        """Convert a study plan document into a Telegram-friendly string."""
        lines = [f"📚 *Study Plan – {plan['exam_or_goal']}*\n"]
        for block in plan.get("blocks", []):
            topic = block.get("topic", "")
            mins = block.get("duration_minutes", 0)
            lines.append(f"• {topic} → {mins} minutes")

        total = plan.get("total_minutes", 0)
        tip = plan.get("tip", "")
        lines.append(f"\n⏱ Total: *{total} minutes*")
        if tip:
            lines.append(f"\n💡 Tip: {tip}")
        return "\n".join(lines)
