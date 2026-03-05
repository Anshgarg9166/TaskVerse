# ─────────────────────────────────────────────
#  Taskverse – Tests: Scheduler Agent
# ─────────────────────────────────────────────
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from agents.scheduler_agent import SchedulerAgent


class TestSchedulerAgent:
    def setup_method(self):
        self.agent = SchedulerAgent()

    def teardown_method(self):
        if self.agent._scheduler.running:
            self.agent.shutdown()

    def test_start_and_stop(self):
        self.agent.start()
        assert self.agent._scheduler.running
        self.agent.shutdown()
        assert not self.agent._scheduler.running

    def test_schedule_reminder(self):
        self.agent.start()
        future = datetime.utcnow() + timedelta(hours=2)

        async def dummy_callback(**kwargs):
            pass

        result = self.agent.schedule_reminder(
            job_id="test_job_1",
            run_at=future,
            callback=dummy_callback,
            telegram_id=12345,
            task_title="Test task",
            task_id="abc123",
        )

        assert result is True
        assert "test_job_1" in self.agent.list_jobs()

    def test_cancel_job(self):
        self.agent.start()
        future = datetime.utcnow() + timedelta(hours=1)

        async def dummy():
            pass

        self.agent.schedule_reminder("cancel_me", future, dummy)
        assert "cancel_me" in self.agent.list_jobs()

        cancelled = self.agent.cancel("cancel_me")
        assert cancelled is True
        assert "cancel_me" not in self.agent.list_jobs()

    def test_cancel_nonexistent_job(self):
        self.agent.start()
        result = self.agent.cancel("does_not_exist")
        assert result is False

    def test_past_deadline_scheduled_soon(self):
        """Past deadlines should be rescheduled to fire in ~5 seconds."""
        self.agent.start()
        past = datetime.utcnow() - timedelta(hours=1)

        async def dummy(**kw):
            pass

        self.agent.schedule_reminder("past_job", past, dummy)
        jobs = self.agent._scheduler.get_jobs()
        job = next((j for j in jobs if j.id == "past_job"), None)
        assert job is not None
        # Should fire very soon (within 10 seconds of now)
        assert (job.next_run_time.replace(tzinfo=None) - datetime.utcnow()).total_seconds() < 10


class TestReminderEngineIntegration:
    @pytest.mark.asyncio
    async def test_poll_upcoming_reminders(self):
        """Polling should schedule jobs for upcoming tasks."""
        mock_task = {
            "_id": "task999",
            "telegram_id": 111,
            "task": "Complete project",
            "deadline": datetime.utcnow() + timedelta(minutes=30),
        }

        with (
            patch("scheduler.reminder_engine.get_database", new=AsyncMock()),
            patch("scheduler.reminder_engine.TaskRepository") as MockRepo,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.get_upcoming.return_value = [mock_task]
            MockRepo.return_value = mock_repo_instance

            from scheduler.reminder_engine import ReminderEngine
            engine = ReminderEngine(send_message=AsyncMock())

            # Patch scheduler to not actually run
            with patch.object(
                engine.__class__.__bases__[0] if hasattr(engine, "__class__") else object,
                "__init__",
                return_value=None,
            ):
                # Directly test the polling logic
                from agents.scheduler_agent import scheduler_agent
                scheduler_agent.start()

                await engine._poll_upcoming_reminders()

                # A job for task999 should have been scheduled
                jobs = scheduler_agent.list_jobs()
                assert "reminder_task999" in jobs

                scheduler_agent.shutdown()
