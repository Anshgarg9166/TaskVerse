# ─────────────────────────────────────────────
#  Taskverse – MongoDB Async Database Layer
# ─────────────────────────────────────────────
from __future__ import annotations

from datetime import datetime
from typing import Any, Dict, List, Optional

import motor.motor_asyncio
from bson import ObjectId
from pymongo import ASCENDING, DESCENDING, IndexModel

from backend.config import get_settings
from utils.logger import log

settings = get_settings()

# ── Client Singleton ──────────────────────────────────────────────────────────

_client: Optional[motor.motor_asyncio.AsyncIOMotorClient] = None
_db: Optional[motor.motor_asyncio.AsyncIOMotorDatabase] = None


async def get_database() -> motor.motor_asyncio.AsyncIOMotorDatabase:
    """Return (and lazily create) the Motor database instance."""
    global _client, _db
    if _db is None:
        _client = motor.motor_asyncio.AsyncIOMotorClient(settings.mongodb_uri)
        _db = _client[settings.mongodb_db_name]
        await _ensure_indexes(_db)
        log.info("MongoDB connected – db={}", settings.mongodb_db_name)
    return _db


async def close_database() -> None:
    """Close the Motor client on shutdown."""
    global _client, _db
    if _client:
        _client.close()
        _client = None
        _db = None
        log.info("MongoDB connection closed")


# ── Index Management ──────────────────────────────────────────────────────────

async def _ensure_indexes(db: motor.motor_asyncio.AsyncIOMotorDatabase) -> None:
    """Create required indexes on first connection."""
    await db.users.create_indexes([
        IndexModel([("telegram_id", ASCENDING)], unique=True),
    ])
    await db.tasks.create_indexes([
        IndexModel([("telegram_id", ASCENDING)]),
        IndexModel([("status", ASCENDING)]),
        IndexModel([("deadline", ASCENDING)]),
    ])
    await db.goals.create_indexes([
        IndexModel([("telegram_id", ASCENDING)]),
    ])
    await db.habits.create_indexes([
        IndexModel([("telegram_id", ASCENDING), ("name", ASCENDING)], unique=True),
    ])
    await db.study_plans.create_indexes([
        IndexModel([("telegram_id", ASCENDING)]),
    ])
    await db.analytics.create_indexes([
        IndexModel([("telegram_id", ASCENDING), ("date", DESCENDING)]),
    ])
    log.debug("MongoDB indexes ensured")


# ── CRUD Helpers ──────────────────────────────────────────────────────────────

def _serialize(doc: Dict[str, Any]) -> Dict[str, Any]:
    """Convert ObjectId → str for JSON serialisation."""
    if doc and "_id" in doc:
        doc["_id"] = str(doc["_id"])
    return doc


class TaskRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.tasks

    async def create(self, data: Dict[str, Any]) -> str:
        data["created_at"] = datetime.utcnow()
        data["updated_at"] = datetime.utcnow()
        result = await self.col.insert_one(data)
        return str(result.inserted_id)

    async def list_by_user(
        self, telegram_id: int, status: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        query: Dict[str, Any] = {"telegram_id": telegram_id}
        if status:
            query["status"] = status
        cursor = self.col.find(query).sort("deadline", ASCENDING)
        return [_serialize(d) async for d in cursor]

    async def get(self, task_id: str) -> Optional[Dict[str, Any]]:
        doc = await self.col.find_one({"_id": ObjectId(task_id)})
        return _serialize(doc) if doc else None

    async def update_status(self, task_id: str, status: str) -> bool:
        result = await self.col.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"status": status, "updated_at": datetime.utcnow()}},
        )
        return result.modified_count > 0

    async def get_upcoming(self, within_minutes: int = 60) -> List[Dict[str, Any]]:
        now = datetime.utcnow()
        from datetime import timedelta
        deadline_limit = now + timedelta(minutes=within_minutes)
        cursor = self.col.find(
            {
                "status": "pending",
                "reminder_sent": False,
                "deadline": {"$gte": now, "$lte": deadline_limit},
            }
        )
        return [_serialize(d) async for d in cursor]

    async def mark_reminder_sent(self, task_id: str) -> None:
        await self.col.update_one(
            {"_id": ObjectId(task_id)},
            {"$set": {"reminder_sent": True, "updated_at": datetime.utcnow()}},
        )


class UserRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.users

    async def upsert(self, data: Dict[str, Any]) -> None:
        await self.col.update_one(
            {"telegram_id": data["telegram_id"]},
            {"$set": {**data, "last_active": datetime.utcnow()}},
            upsert=True,
        )

    async def get(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        doc = await self.col.find_one({"telegram_id": telegram_id})
        return _serialize(doc) if doc else None


class GoalRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.goals

    async def create(self, data: Dict[str, Any]) -> str:
        data["created_at"] = datetime.utcnow()
        result = await self.col.insert_one(data)
        return str(result.inserted_id)

    async def list_by_user(self, telegram_id: int) -> List[Dict[str, Any]]:
        cursor = self.col.find({"telegram_id": telegram_id}).sort("created_at", DESCENDING)
        return [_serialize(d) async for d in cursor]


class HabitRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.habits

    async def upsert(self, data: Dict[str, Any]) -> str:
        result = await self.col.find_one_and_update(
            {"telegram_id": data["telegram_id"], "name": data["name"]},
            {"$set": data},
            upsert=True,
            return_document=True,
        )
        return str(result["_id"])

    async def list_by_user(self, telegram_id: int) -> List[Dict[str, Any]]:
        cursor = self.col.find({"telegram_id": telegram_id})
        return [_serialize(d) async for d in cursor]

    async def increment_streak(self, telegram_id: int, habit_name: str) -> None:
        await self.col.update_one(
            {"telegram_id": telegram_id, "name": habit_name},
            {"$inc": {"streak": 1}},
        )


class StudyPlanRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.study_plans

    async def create(self, data: Dict[str, Any]) -> str:
        data["created_at"] = datetime.utcnow()
        result = await self.col.insert_one(data)
        return str(result.inserted_id)

    async def list_by_user(self, telegram_id: int) -> List[Dict[str, Any]]:
        cursor = self.col.find({"telegram_id": telegram_id}).sort("created_at", DESCENDING)
        return [_serialize(d) async for d in cursor]


class AnalyticsRepository:
    def __init__(self, db: motor.motor_asyncio.AsyncIOMotorDatabase):
        self.col = db.analytics

    async def increment(self, telegram_id: int, field: str, amount: int = 1) -> None:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        await self.col.update_one(
            {"telegram_id": telegram_id, "date": today},
            {"$inc": {field: amount}},
            upsert=True,
        )

    async def get_today(self, telegram_id: int) -> Optional[Dict[str, Any]]:
        today = datetime.utcnow().replace(hour=0, minute=0, second=0, microsecond=0)
        doc = await self.col.find_one({"telegram_id": telegram_id, "date": today})
        return _serialize(doc) if doc else None
