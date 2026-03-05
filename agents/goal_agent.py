# ─────────────────────────────────────────────
#  Taskverse – Goal Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from typing import Any, Dict, List

from database.db import GoalRepository, get_database
from llm.groq_client import chat_completion_json
from llm.prompts import GOAL_PLANNING_SYSTEM, goal_planning_user
from utils.logger import log


class GoalAgent:
    """
    Breaks long-term goals into structured sub-tasks using the LLM
    and persists the goal plan to MongoDB.
    """

    async def create_goal(
        self, telegram_id: int, goal_text: str
    ) -> Dict[str, Any]:
        """
        Pipeline: LLM goal decomposition → DB insert.

        Returns the saved goal document.
        """
        log.info("GoalAgent.create_goal – user={} goal={!r}", telegram_id, goal_text)

        # 1. LLM decomposition
        parsed = await chat_completion_json(
            GOAL_PLANNING_SYSTEM,
            goal_planning_user(goal_text),
        )

        if not parsed or "goal_title" not in parsed:
            log.warning("GoalAgent: LLM fallback for goal={!r}", goal_text)
            parsed = {
                "goal_title": goal_text,
                "description": "",
                "sub_tasks": [{"title": "Research and plan the goal"}],
            }

        # 2. Build document
        sub_tasks = [
            {"title": t.get("title", ""), "status": "pending"}
            for t in parsed.get("sub_tasks", [])
        ]

        goal_doc: Dict[str, Any] = {
            "telegram_id": telegram_id,
            "title": parsed.get("goal_title", goal_text)[:200],
            "description": parsed.get("description", ""),
            "sub_tasks": sub_tasks,
            "status": "active",
        }

        # 3. Persist
        db = await get_database()
        repo = GoalRepository(db)
        goal_id = await repo.create(goal_doc)
        goal_doc["_id"] = goal_id

        log.info("GoalAgent: goal created – id={} title={!r}", goal_id, goal_doc["title"])
        return goal_doc

    async def list_goals(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Return all goals for a user."""
        db = await get_database()
        repo = GoalRepository(db)
        return await repo.list_by_user(telegram_id)
