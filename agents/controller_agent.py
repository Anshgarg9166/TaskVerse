# ─────────────────────────────────────────────
#  Taskverse – Controller Agent (Main Brain)
# ─────────────────────────────────────────────
"""
Orchestrates the entire agent pipeline.

Flow
────
IncomingMessage → detect_intent → dispatch to specialist agent
             → build reply string → return to Telegram handler
"""
from __future__ import annotations

from typing import Any, Callable, Dict, Optional

from agents.goal_agent import GoalAgent
from agents.habit_agent import HabitAgent
from agents.input_agent import IncomingMessage
from agents.motivation_agent import MotivationAgent
from agents.scheduler_agent import scheduler_agent
from agents.study_agent import StudyAgent
from agents.task_agent import TaskAgent
from database.db import UserRepository, get_database
from llm.groq_client import chat_completion_json
from llm.prompts import INTENT_DETECTION_SYSTEM, intent_detection_user
from utils.helpers import humanise_delta
from utils.logger import log


class ControllerAgent:
    """
    The Main Brain of Taskverse.

    Responsibilities
    ────────────────
    1. Detect user intent (LLM-powered).
    2. Dispatch to the appropriate specialist agent.
    3. Schedule reminders when tasks are created.
    4. Format and return the reply string.
    """

    def __init__(self, send_message: Callable) -> None:
        """
        Parameters
        ----------
        send_message : async callable
            Function signature: (telegram_id: int, text: str) → None
            Used by the scheduler to push late notifications.
        """
        self._send = send_message
        self._task_agent = TaskAgent()
        self._goal_agent = GoalAgent()
        self._study_agent = StudyAgent()
        self._habit_agent = HabitAgent()
        self._motivation_agent = MotivationAgent()

    # ── Public Entry Point ────────────────────────────────────────────────────

    async def handle(self, msg: IncomingMessage) -> str:
        """
        Process an IncomingMessage and return a reply string.
        """
        await self._upsert_user(msg)

        # Command-based routing takes priority over NLP intent
        if msg.command:
            return await self._route_command(msg)

        # NLP intent fallback for plain messages
        return await self._route_by_intent(msg)

    # ── Command Router ────────────────────────────────────────────────────────

    async def _route_command(self, msg: IncomingMessage) -> str:
        handlers: Dict[str, Callable] = {
            "start":      self._cmd_start,
            "add":        self._cmd_add,
            "tasks":      self._cmd_tasks,
            "done":       self._cmd_done,
            "delay":      self._cmd_delay,
            "goal":       self._cmd_goal,
            "studyplan":  self._cmd_studyplan,
            "habits":     self._cmd_habits,
            "motivation": self._cmd_motivation,
            "help":       self._cmd_help,
        }
        handler = handlers.get(msg.command)
        if handler:
            return await handler(msg)
        return f"Unknown command /{msg.command}. Try /help."

    # ── NLP Intent Router ─────────────────────────────────────────────────────

    async def _route_by_intent(self, msg: IncomingMessage) -> str:
        intent_data = await chat_completion_json(
            INTENT_DETECTION_SYSTEM,
            intent_detection_user(msg.raw_text),
        )
        intent = intent_data.get("intent", "unknown")
        confidence = intent_data.get("confidence", 0.0)

        log.info(
            "ControllerAgent intent={} confidence={:.2f} user={}",
            intent, confidence, msg.telegram_id,
        )

        if confidence < 0.5:
            return (
                "I'm not sure what you mean 🤔\n"
                "Try a command like /add, /goal, /studyplan or just type your task!"
            )

        fake_cmd = IncomingMessage(
            telegram_id=msg.telegram_id,
            username=msg.username,
            first_name=msg.first_name,
            raw_text=msg.raw_text,
            command=self._intent_to_command(intent),
            command_args=msg.raw_text,
        )
        return await self._route_command(fake_cmd)

    def _intent_to_command(self, intent: str) -> str:
        mapping = {
            "create_task":        "add",
            "list_tasks":         "tasks",
            "complete_task":      "done",
            "delay_task":         "delay",
            "goal_creation":      "goal",
            "study_plan":         "studyplan",
            "habit_update":       "habits",
            "motivation_request": "motivation",
        }
        return mapping.get(intent, "help")

    # ── Command Handlers ──────────────────────────────────────────────────────

    async def _cmd_start(self, msg: IncomingMessage) -> str:
        name = msg.first_name or "there"
        return (
            f"👋 Hey {name}! Welcome to *Taskverse* – your AI productivity assistant.\n\n"
            "Here's what I can do:\n"
            "• /add <task> – Add a new task\n"
            "• /tasks – View your pending tasks\n"
            "• /done <task_id> – Mark a task complete\n"
            "• /delay <task_id> <new deadline> – Reschedule a task\n"
            "• /goal <your goal> – Break a goal into action steps\n"
            "• /studyplan <topics> – Generate a study schedule\n"
            "• /habits <habit name> – Track a habit\n"
            "• /motivation – Get a boost of motivation\n\n"
            "Let's get productive! 🚀"
        )

    async def _cmd_help(self, msg: IncomingMessage) -> str:
        return await self._cmd_start(msg)

    async def _cmd_add(self, msg: IncomingMessage) -> str:
        text = msg.command_args.strip()
        if not text:
            return "Please provide a task. Example:\n/add Finish Echoverse backend tomorrow evening"

        task = await self._task_agent.create_task(msg.telegram_id, text)

        # Schedule reminder if deadline is set
        deadline = task.get("deadline")
        if deadline:
            job_id = f"reminder_{task['_id']}"
            scheduler_agent.schedule_reminder(
                job_id=job_id,
                run_at=deadline,
                callback=self._send_reminder,
                telegram_id=msg.telegram_id,
                task_title=task["task"],
                task_id=task["_id"],
            )
            deadline_str = humanise_delta(deadline)
            return (
                f"✅ *Task added!*\n\n"
                f"📌 {task['task']}\n"
                f"⏰ Deadline: {deadline_str}\n"
                f"🎯 Priority: {task['priority'].upper()}\n\n"
                f"Reminder scheduled!"
            )

        return (
            f"✅ *Task added!*\n\n"
            f"📌 {task['task']}\n"
            f"🎯 Priority: {task['priority'].upper()}"
        )

    async def _cmd_tasks(self, msg: IncomingMessage) -> str:
        tasks = await self._task_agent.list_tasks(msg.telegram_id, status="pending")
        if not tasks:
            return "🎉 No pending tasks! You're all caught up."

        lines = ["📋 *Your Pending Tasks*\n"]
        for i, t in enumerate(tasks[:10], 1):
            title = t.get("task", "")
            priority = t.get("priority", "medium").upper()
            deadline = t.get("deadline")
            dl_str = f" | Due: {humanise_delta(deadline)}" if deadline else ""
            task_id_short = t.get("_id", "")[-6:]
            lines.append(f"{i}. {title} [{priority}]{dl_str}\n   ID: `…{task_id_short}`")

        return "\n".join(lines)

    async def _cmd_done(self, msg: IncomingMessage) -> str:
        task_id = msg.command_args.strip()
        if not task_id:
            return "Provide the task ID. Get it from /tasks.\nExample: /done 664f..."

        success = await self._task_agent.complete_task(task_id, msg.telegram_id)
        if success:
            scheduler_agent.cancel(f"reminder_{task_id}")
            return "🎉 Task marked as *done*! Keep up the great work!"
        return "❌ Task not found. Check the ID with /tasks."

    async def _cmd_delay(self, msg: IncomingMessage) -> str:
        parts = msg.command_args.strip().split(maxsplit=1)
        if len(parts) < 2:
            return "Usage: /delay <task_id> <new deadline>\nExample: /delay 664f... tomorrow morning"

        task_id, new_deadline = parts[0], parts[1]
        success = await self._task_agent.delay_task(task_id, new_deadline)
        if success:
            return f"⏰ Task rescheduled to *{new_deadline}*."
        return "❌ Could not reschedule. Check the task ID or deadline format."

    async def _cmd_goal(self, msg: IncomingMessage) -> str:
        goal_text = msg.command_args.strip()
        if not goal_text:
            return "Tell me your goal! Example:\n/goal Get a software engineering internship"

        goal = await self._goal_agent.create_goal(msg.telegram_id, goal_text)

        lines = [f"🎯 *Goal: {goal['title']}*\n"]
        if goal.get("description"):
            lines.append(f"_{goal['description']}_\n")
        lines.append("*Action Steps:*")
        for i, sub in enumerate(goal.get("sub_tasks", []), 1):
            lines.append(f"{i}. {sub['title']}")

        return "\n".join(lines)

    async def _cmd_studyplan(self, msg: IncomingMessage) -> str:
        topics = msg.command_args.strip()
        if not topics:
            return "What do you want to study? Example:\n/studyplan DSA, DBMS, and OS for exam"

        plan = await self._study_agent.create_study_plan(msg.telegram_id, topics)
        return self._study_agent.format_plan_message(plan)

    async def _cmd_habits(self, msg: IncomingMessage) -> str:
        habit_name = msg.command_args.strip()

        if not habit_name:
            habits = await self._habit_agent.get_habits(msg.telegram_id)
            return self._habit_agent.format_habits_message(habits)

        result = await self._habit_agent.log_habit(msg.telegram_id, habit_name)
        streak = result.get("streak", 0)
        rate = result.get("completion_rate", 0.0)
        return (
            f"✅ *{habit_name}* logged!\n"
            f"🔥 Streak: {streak} days\n"
            f"📊 Completion rate: {rate}%"
        )

    async def _cmd_motivation(self, msg: IncomingMessage) -> str:
        return await self._motivation_agent.get_motivation(msg.telegram_id)

    # ── Reminder Callback ─────────────────────────────────────────────────────

    async def _send_reminder(
        self, telegram_id: int, task_title: str, task_id: str
    ) -> None:
        """Called by APScheduler when a reminder fires."""
        text = (
            f"⏰ *Reminder!*\n\n"
            f"Your task is due:\n📌 {task_title}\n\n"
            f"Mark it done with:\n/done {task_id}"
        )
        await self._send(telegram_id, text)

        # Mark reminder as sent in DB
        db = await get_database()
        from database.db import TaskRepository
        repo = TaskRepository(db)
        await repo.mark_reminder_sent(task_id)
        log.info("ControllerAgent: reminder sent – user={} task={}", telegram_id, task_id)

    # ── Helpers ───────────────────────────────────────────────────────────────

    async def _upsert_user(self, msg: IncomingMessage) -> None:
        db = await get_database()
        repo = UserRepository(db)
        await repo.upsert(
            {
                "telegram_id": msg.telegram_id,
                "username": msg.username,
                "first_name": msg.first_name,
            }
        )
