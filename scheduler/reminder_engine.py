# ─────────────────────────────────────────────
#  Taskverse – Reminder Engine
# ─────────────────────────────────────────────
"""
Background polling loop that:
1. Scans for tasks due within the next 60 minutes.
2. Schedules one-shot reminders via SchedulerAgent.
3. Sends a daily morning summary at 08:00.
"""
from __future__ import annotations

from datetime import datetime
from typing import Callable

from agents.scheduler_agent import scheduler_agent
from database.db import TaskRepository, get_database
from utils.helpers import humanise_delta
from utils.logger import log


class ReminderEngine:
    """
    High-level background engine that keeps reminders synced with the DB.
    """

    def __init__(self, send_message: Callable) -> None:
        self._send = send_message

    def start(self) -> None:
        """Register recurring jobs on the shared scheduler."""
        # Poll for upcoming tasks every 5 minutes
        scheduler_agent.schedule_interval(
            job_id="reminder_poller",
            seconds=300,
            callback=self._poll_upcoming_reminders,
        )

        # Daily summary every morning at 08:00 (UTC)
        from apscheduler.triggers.cron import CronTrigger
        scheduler_agent._scheduler.add_job(
            self._send_daily_summary,
            trigger=CronTrigger(hour=8, minute=0),
            id="daily_summary",
            replace_existing=True,
        )

        log.info("ReminderEngine started – poller=5min, daily-summary=08:00 UTC")

    # ── Polling Job ───────────────────────────────────────────────────────────

    async def _poll_upcoming_reminders(self) -> None:
        """Find tasks due within 60 minutes and ensure reminders are queued."""
        try:
            db = await get_database()
            repo = TaskRepository(db)
            upcoming = await repo.get_upcoming(within_minutes=60)

            for task in upcoming:
                task_id = task["_id"]
                job_id = f"reminder_{task_id}"

                # Only schedule if not already queued
                if job_id not in scheduler_agent.list_jobs():
                    deadline: datetime = task.get("deadline")
                    if deadline:
                        scheduler_agent.schedule_reminder(
                            job_id=job_id,
                            run_at=deadline,
                            callback=self._fire_reminder,
                            telegram_id=task["telegram_id"],
                            task_title=task["task"],
                            task_id=task_id,
                        )

            if upcoming:
                log.debug("ReminderEngine: polled {} upcoming tasks", len(upcoming))

        except Exception as exc:
            log.error("ReminderEngine._poll_upcoming_reminders error: {}", exc)

    async def _fire_reminder(
        self, telegram_id: int, task_title: str, task_id: str
    ) -> None:
        """Send the reminder Telegram message and update the DB."""
        try:
            text = (
                f"⏰ *Task Reminder*\n\n"
                f"📌 {task_title}\n\n"
                f"Mark it done: /done {task_id}"
            )
            await self._send(telegram_id, text)

            db = await get_database()
            repo = TaskRepository(db)
            await repo.mark_reminder_sent(task_id)
            log.info("ReminderEngine: fired reminder – user={} task={}", telegram_id, task_id)

        except Exception as exc:
            log.error("ReminderEngine._fire_reminder error: {}", exc)

    # ── Daily Summary ─────────────────────────────────────────────────────────

    async def _send_daily_summary(self) -> None:
        """Send a morning task summary to all active users."""
        try:
            db = await get_database()
            users_col = db.users
            cursor = users_col.find({})

            count = 0
            async for user in cursor:
                telegram_id = user.get("telegram_id")
                if not telegram_id:
                    continue

                repo = TaskRepository(db)
                tasks = await repo.list_by_user(telegram_id, status="pending")

                if not tasks:
                    continue

                lines = ["🌅 *Good morning! Here's your task list:*\n"]
                for i, t in enumerate(tasks[:5], 1):
                    deadline = t.get("deadline")
                    dl_str = f" – due {humanise_delta(deadline)}" if deadline else ""
                    lines.append(f"{i}. {t['task']}{dl_str}")

                if len(tasks) > 5:
                    lines.append(f"\n…and {len(tasks) - 5} more. Check /tasks")

                await self._send(telegram_id, "\n".join(lines))
                count += 1

            log.info("ReminderEngine: daily summary sent to {} users", count)

        except Exception as exc:
            log.error("ReminderEngine._send_daily_summary error: {}", exc)
