# ─────────────────────────────────────────────
#  Taskverse – Habit & Analytics Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List

from database.db import AnalyticsRepository, HabitRepository, get_database
from utils.logger import log


class HabitAgent:
    """
    Tracks user habits, updates streaks, and computes analytics.
    """

    async def log_habit(
        self, telegram_id: int, habit_name: str, completed: bool = True
    ) -> Dict[str, Any]:
        """
        Record a habit entry, update the streak, and return the updated doc.
        """
        log.info(
            "HabitAgent.log_habit – user={} habit={!r} completed={}",
            telegram_id,
            habit_name,
            completed,
        )
        db = await get_database()
        repo = HabitRepository(db)

        # Fetch existing or create new
        existing = await repo.col.find_one(
            {"telegram_id": telegram_id, "name": habit_name}
        )

        entry = {"date": datetime.utcnow(), "completed": completed}

        if existing:
            entries = existing.get("entries", [])
            entries.append(entry)
            total = len(entries)
            done = sum(1 for e in entries if e.get("completed"))
            rate = round(done / total * 100, 1) if total else 0.0
            streak = existing.get("streak", 0) + (1 if completed else 0)

            await repo.col.update_one(
                {"telegram_id": telegram_id, "name": habit_name},
                {
                    "$push": {"entries": entry},
                    "$set": {"streak": streak, "completion_rate": rate},
                },
            )
        else:
            streak = 1 if completed else 0
            rate = 100.0 if completed else 0.0
            await repo.upsert(
                {
                    "telegram_id": telegram_id,
                    "name": habit_name,
                    "streak": streak,
                    "completion_rate": rate,
                    "entries": [entry],
                }
            )

        # Analytics bump
        if completed:
            analytics = AnalyticsRepository(db)
            await analytics.increment(telegram_id, "habits_completed")

        result = await repo.col.find_one(
            {"telegram_id": telegram_id, "name": habit_name}
        )
        result["_id"] = str(result["_id"])
        return result

    async def get_habits(self, telegram_id: int) -> List[Dict[str, Any]]:
        """Return all habits for a user."""
        db = await get_database()
        repo = HabitRepository(db)
        return await repo.list_by_user(telegram_id)

    def format_habits_message(self, habits: List[Dict[str, Any]]) -> str:
        """Format habits list as a Telegram-friendly string."""
        if not habits:
            return "No habits tracked yet. Start with /habits <habit_name>"

        lines = ["🔥 *Your Habits*\n"]
        for h in habits:
            name = h.get("name", "")
            streak = h.get("streak", 0)
            rate = h.get("completion_rate", 0.0)
            lines.append(f"• *{name}* – streak: {streak} days | rate: {rate}%")
        return "\n".join(lines)
