# ─────────────────────────────────────────────
#  Taskverse – Telegram Bot Bootstrap
# ─────────────────────────────────────────────
from __future__ import annotations

from telegram import Bot
from telegram.constants import ParseMode
from telegram.ext import Application, ContextTypes

from agents.controller_agent import ControllerAgent
from agents.scheduler_agent import scheduler_agent
from backend.config import get_settings
from database.db import close_database, get_database
from scheduler.reminder_engine import ReminderEngine
from telegram_bot.handlers import register_handlers
from utils.logger import log

settings = get_settings()


async def send_message(telegram_id: int, text: str) -> None:
    """Push a message to a Telegram user."""
    bot = Bot(token=settings.telegram_bot_token)
    try:
        await bot.send_message(
            chat_id=telegram_id,
            text=text,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        log.error("send_message failed – user={} err={}", telegram_id, exc)
    finally:
        await bot.close()


async def _post_init(application: Application) -> None:
    """
    Runs inside PTB's event loop after the Application is initialised.
    Safe place to do async startup: DB check, scheduler start, etc.
    """
    # Verify MongoDB
    try:
        db = await get_database()
        await db.command("ping")
        log.info("✅ MongoDB connection verified")
    except Exception as exc:
        log.error("❌ MongoDB connection failed: {}", exc)
        raise

    # Start scheduler + reminder engine
    scheduler_agent.start()
    reminder_engine: ReminderEngine = application.bot_data["reminder_engine"]
    reminder_engine.start()

    log.info("✅ Scheduler and reminder engine started")


async def _post_shutdown(application: Application) -> None:
    """Runs inside PTB's event loop on shutdown."""
    await close_database()
    scheduler_agent.shutdown()
    log.info("Taskverse shut down cleanly. Goodbye!")


def build_application() -> Application:
    """
    Build and configure the Telegram Application.
    All async init is deferred to post_init so PTB owns the event loop.
    """
    app = (
        Application.builder()
        .token(settings.telegram_bot_token)
        .post_init(_post_init)
        .post_shutdown(_post_shutdown)
        .build()
    )

    controller = ControllerAgent(send_message=send_message)
    reminder_engine = ReminderEngine(send_message=send_message)

    # Store reminder_engine so post_init can access it
    app.bot_data["reminder_engine"] = reminder_engine

    # Register all Telegram handlers
    register_handlers(app, controller)

    log.info("Taskverse Telegram bot application built and ready")
    return app