# ─────────────────────────────────────────────
#  Taskverse – Scheduler Agent
# ─────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Callable, Coroutine

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.date import DateTrigger
from apscheduler.triggers.interval import IntervalTrigger

from utils.logger import log


def utcnow() -> datetime:
    """Return current UTC time as timezone-aware datetime."""
    return datetime.now(timezone.utc)


class SchedulerAgent:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    def start(self) -> None:
        if not self._scheduler.running:
            self._scheduler.start()
            log.info("SchedulerAgent started")

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)
            log.info("SchedulerAgent stopped")

    def schedule_reminder(
        self,
        job_id: str,
        run_at: datetime,
        callback: Callable[..., Coroutine],
        **kwargs: Any,
    ) -> bool:
        # Ensure run_at is timezone-aware
        if run_at.tzinfo is None:
            run_at = run_at.replace(tzinfo=timezone.utc)

        now = utcnow()
        if run_at <= now:
            log.debug("SchedulerAgent: run_at is in the past, firing in 5s – {}", job_id)
            run_at = now + timedelta(seconds=5)

        try:
            self._scheduler.remove_job(job_id)
        except Exception:
            pass

        self._scheduler.add_job(
            callback,
            trigger=DateTrigger(run_date=run_at),
            id=job_id,
            kwargs=kwargs,
            replace_existing=True,
            misfire_grace_time=300,
        )

        log.info("SchedulerAgent: reminder scheduled – id={} at={}", job_id, run_at)
        return True

    def schedule_interval(
        self,
        job_id: str,
        seconds: int,
        callback: Callable[..., Coroutine],
        **kwargs: Any,
    ) -> None:
        self._scheduler.add_job(
            callback,
            trigger=IntervalTrigger(seconds=seconds),
            id=job_id,
            kwargs=kwargs,
            replace_existing=True,
        )
        log.info("SchedulerAgent: interval job registered – id={} every={}s", job_id, seconds)

    def cancel(self, job_id: str) -> bool:
        try:
            self._scheduler.remove_job(job_id)
            log.info("SchedulerAgent: cancelled job – id={}", job_id)
            return True
        except Exception:
            return False

    def list_jobs(self) -> list[str]:
        return [job.id for job in self._scheduler.get_jobs()]


# Module-level singleton
scheduler_agent = SchedulerAgent()