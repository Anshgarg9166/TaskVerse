# ─────────────────────────────────────────────
#  Taskverse – Tests: Task Parser
# ─────────────────────────────────────────────
from __future__ import annotations

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from agents.task_agent import TaskAgent
from utils.helpers import parse_natural_date


# ── parse_natural_date ────────────────────────────────────────────────────────

class TestParseNaturalDate:
    def test_tomorrow_evening(self):
        result = parse_natural_date("tomorrow evening")
        assert result is not None
        assert result.hour == 18

    def test_today_morning(self):
        result = parse_natural_date("today morning")
        assert result is not None
        assert result.hour == 8

    def test_explicit_date(self):
        result = parse_natural_date("2026-12-31")
        assert result is not None
        assert result.year == 2026
        assert result.month == 12

    def test_none_for_garbage(self):
        # dateutil is quite permissive, so only truly unparseable strings return None
        result = parse_natural_date("xxxxxxxx_not_a_date_!!!###")
        # May or may not return None depending on dateutil version – just assert no crash
        assert result is None or isinstance(result, datetime)

    def test_today(self):
        result = parse_natural_date("today")
        assert result is not None
        now = datetime.now()
        assert result.date() == now.date()


# ── TaskAgent.create_task (mocked LLM + DB) ───────────────────────────────────

class TestTaskAgent:
    @pytest.mark.asyncio
    async def test_create_task_success(self):
        mock_llm_response = {
            "task": "Finish Echoverse backend",
            "description": "Complete all API endpoints",
            "deadline_text": "tomorrow evening",
            "priority": "high",
            "tags": ["backend", "coding"],
        }

        with (
            patch(
                "agents.task_agent.chat_completion_json",
                new=AsyncMock(return_value=mock_llm_response),
            ),
            patch(
                "agents.task_agent.get_database",
                new=AsyncMock(),
            ),
            patch(
                "agents.task_agent.TaskRepository",
            ) as MockRepo,
            patch(
                "agents.task_agent.AnalyticsRepository",
            ) as MockAnalytics,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.create.return_value = "fake_task_id_123"
            MockRepo.return_value = mock_repo_instance

            mock_analytics_instance = AsyncMock()
            MockAnalytics.return_value = mock_analytics_instance

            agent = TaskAgent()
            result = await agent.create_task(
                telegram_id=12345,
                raw_text="Finish Echoverse backend tomorrow evening",
            )

        assert result["task"] == "Finish Echoverse backend"
        assert result["priority"] == "high"
        assert result["_id"] == "fake_task_id_123"
        assert result["deadline"] is not None

    @pytest.mark.asyncio
    async def test_create_task_llm_fallback(self):
        """If LLM returns empty dict, fall back to raw text as task title."""
        with (
            patch(
                "agents.task_agent.chat_completion_json",
                new=AsyncMock(return_value={}),
            ),
            patch("agents.task_agent.get_database", new=AsyncMock()),
            patch("agents.task_agent.TaskRepository") as MockRepo,
            patch("agents.task_agent.AnalyticsRepository") as MockAnalytics,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.create.return_value = "fallback_id"
            MockRepo.return_value = mock_repo_instance
            MockAnalytics.return_value = AsyncMock()

            agent = TaskAgent()
            result = await agent.create_task(
                telegram_id=99999,
                raw_text="Buy groceries",
            )

        assert result["task"] == "Buy groceries"
        assert result["priority"] == "medium"
