# ─────────────────────────────────────────────
#  Taskverse – Task Intelligence Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from database.db import AnalyticsRepository, TaskRepository, get_database
from llm.groq_client import chat_completion_json
from llm.prompts import TASK_EXTRACTION_SYSTEM, task_extraction_user
from utils.helpers import parse_natural_date
from utils.logger import log


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class TaskAgent:
    """
    Uses the LLM to convert natural-language input into structured tasks,
    persists them to MongoDB, and returns confirmation data.
    """

    async def create_task(
        self, telegram_id: int, raw_text: str
    ) -> Dict[str, Any]:
        log.info("TaskAgent.create_task – user={} text={!r}", telegram_id, raw_text)

        # 1. LLM extraction
        parsed = await chat_completion_json(
            TASK_EXTRACTION_SYSTEM,
            task_extraction_user(raw_text),
        )

        if not parsed or "task" not in parsed:
            log.warning("TaskAgent: LLM did not return valid task JSON, using fallback")
            parsed = {"task": raw_text, "priority": "medium"}

        # 2. Deadline resolution
        deadline: Optional[datetime] = None
        deadline_text = parsed.get("deadline_text")
        if deadline_text:
            deadline = parse_natural_date(deadline_text)
            if not deadline:
                log.debug("TaskAgent: could not parse deadline_text={!r}", deadline_text)

        # 3. Build document — store deadline as UTC naive for MongoDB
        deadline_utc = None
        if deadline is not None:
            if deadline.tzinfo is not None:
                deadline_utc = deadline.astimezone(timezone.utc).replace(tzinfo=None)
            else:
                deadline_utc = deadline

        task_doc: Dict[str, Any] = {
            "telegram_id": telegram_id,
            "task": parsed.get("task", raw_text)[:200],
            "description": parsed.get("description"),
            "deadline": deadline_utc,
            "priority": parsed.get("priority", "medium"),
            "status": "pending",
            "reminder_sent": False,
            "tags": parsed.get("tags", []),
        }

        # 4. Persist
        db = await get_database()
        repo = TaskRepository(db)
        task_id = await repo.create(task_doc)
        task_doc["_id"] = task_id

        # 5. Analytics
        analytics = AnalyticsRepository(db)
        await analytics.increment(telegram_id, "tasks_created")

        log.info("TaskAgent: task created – id={} title={!r}", task_id, task_doc["task"])
        return task_doc

    async def list_tasks(
        self, telegram_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        db = await get_database()
        repo = TaskRepository(db)
        return await repo.list_by_user(telegram_id, status=status)

    async def complete_task(self, task_id: str, telegram_id: int) -> bool:
        db = await get_database()
        repo = TaskRepository(db)
        updated = await repo.update_status(task_id, "done")
        if updated:
            analytics = AnalyticsRepository(db)
            await analytics.increment(telegram_id, "tasks_completed")
        return updated

    async def delay_task(self, task_id: str, new_deadline_text: str) -> bool:
        new_deadline = parse_natural_date(new_deadline_text)
        if not new_deadline:
            return False

        # Convert to UTC naive for MongoDB
        if new_deadline.tzinfo is not None:
            new_deadline = new_deadline.astimezone(timezone.utc).replace(tzinfo=None)

        from bson import ObjectId
        db = await get_database()
        repo = TaskRepository(db)
        result = await repo.col.update_one(
            {"_id": ObjectId(task_id)},
            {
                "$set": {
                    "deadline": new_deadline,
                    "status": "delayed",
                    "reminder_sent": False,
                    "updated_at": utcnow().replace(tzinfo=None),
                }
            },
        )
        return result.modified_count > 0