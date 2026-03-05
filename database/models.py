# ─────────────────────────────────────────────
#  Taskverse – Pydantic Data Models
# ─────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, Field


# ── Enums ─────────────────────────────────────────────────────────────────────

class Priority(str, Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"


class TaskStatus(str, Enum):
    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    DONE = "done"
    DELAYED = "delayed"


class GoalStatus(str, Enum):
    ACTIVE = "active"
    COMPLETED = "completed"
    PAUSED = "paused"


# ── User ──────────────────────────────────────────────────────────────────────

class User(BaseModel):
    telegram_id: int
    username: Optional[str] = None
    first_name: Optional[str] = None
    timezone: str = "Asia/Kolkata"
    created_at: datetime = Field(default_factory=datetime.utcnow)
    last_active: datetime = Field(default_factory=datetime.utcnow)


# ── Task ──────────────────────────────────────────────────────────────────────

class Task(BaseModel):
    telegram_id: int
    task: str
    description: Optional[str] = None
    deadline: Optional[datetime] = None
    priority: Priority = Priority.MEDIUM
    status: TaskStatus = TaskStatus.PENDING
    reminder_sent: bool = False
    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


# ── Goal ──────────────────────────────────────────────────────────────────────

class GoalTask(BaseModel):
    title: str
    status: TaskStatus = TaskStatus.PENDING


class Goal(BaseModel):
    telegram_id: int
    title: str
    description: Optional[str] = None
    sub_tasks: List[GoalTask] = []
    status: GoalStatus = GoalStatus.ACTIVE
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Habit ─────────────────────────────────────────────────────────────────────

class HabitEntry(BaseModel):
    date: datetime
    completed: bool


class Habit(BaseModel):
    telegram_id: int
    name: str
    streak: int = 0
    completion_rate: float = 0.0
    entries: List[HabitEntry] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Study Plan ────────────────────────────────────────────────────────────────

class StudyBlock(BaseModel):
    topic: str
    duration_minutes: int


class StudyPlan(BaseModel):
    telegram_id: int
    exam_or_goal: str
    blocks: List[StudyBlock] = []
    created_at: datetime = Field(default_factory=datetime.utcnow)


# ── Analytics ─────────────────────────────────────────────────────────────────

class Analytics(BaseModel):
    telegram_id: int
    date: datetime = Field(default_factory=datetime.utcnow)
    tasks_created: int = 0
    tasks_completed: int = 0
    habits_completed: int = 0
    motivation_sent: int = 0
