# ─────────────────────────────────────────────
#  Taskverse – Tests: Goal Generation
# ─────────────────────────────────────────────
from __future__ import annotations

import sys, os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from unittest.mock import AsyncMock, patch

import pytest

from agents.goal_agent import GoalAgent


class TestGoalAgent:
    @pytest.mark.asyncio
    async def test_create_goal_success(self):
        mock_llm_response = {
            "goal_title": "Get a Software Engineering Internship",
            "description": "Land a SWE internship at a top tech company",
            "sub_tasks": [
                {"title": "Practice DSA on LeetCode daily"},
                {"title": "Build 2 portfolio projects"},
                {"title": "Polish resume and LinkedIn"},
                {"title": "Apply to 10 companies per week"},
                {"title": "Prepare for system design interviews"},
            ],
        }

        with (
            patch(
                "agents.goal_agent.chat_completion_json",
                new=AsyncMock(return_value=mock_llm_response),
            ),
            patch("agents.goal_agent.get_database", new=AsyncMock()),
            patch("agents.goal_agent.GoalRepository") as MockRepo,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.create.return_value = "goal_id_abc"
            MockRepo.return_value = mock_repo_instance

            agent = GoalAgent()
            result = await agent.create_goal(
                telegram_id=12345,
                goal_text="get software engineering internship",
            )

        assert result["title"] == "Get a Software Engineering Internship"
        assert len(result["sub_tasks"]) == 5
        assert result["sub_tasks"][0]["title"] == "Practice DSA on LeetCode daily"
        assert result["status"] == "active"

    @pytest.mark.asyncio
    async def test_create_goal_llm_fallback(self):
        """Empty LLM response triggers fallback sub-task."""
        with (
            patch(
                "agents.goal_agent.chat_completion_json",
                new=AsyncMock(return_value={}),
            ),
            patch("agents.goal_agent.get_database", new=AsyncMock()),
            patch("agents.goal_agent.GoalRepository") as MockRepo,
        ):
            mock_repo_instance = AsyncMock()
            mock_repo_instance.create.return_value = "fallback_goal_id"
            MockRepo.return_value = mock_repo_instance

            agent = GoalAgent()
            result = await agent.create_goal(
                telegram_id=99,
                goal_text="Learn machine learning",
            )

        assert result["title"] == "Learn machine learning"
        assert len(result["sub_tasks"]) >= 1
