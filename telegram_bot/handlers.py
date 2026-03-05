# ─────────────────────────────────────────────
#  Taskverse – Telegram Bot Handlers
# ─────────────────────────────────────────────
from __future__ import annotations

from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CommandHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from agents.controller_agent import ControllerAgent
from agents.input_agent import InputAgent, IncomingMessage
from utils.logger import log

_input_agent = InputAgent()


def _update_to_dict(update: Update) -> dict:
    if update.message:
        msg = update.message
        return {
            "message": {
                "from": {
                    "id": msg.from_user.id if msg.from_user else 0,
                    "username": msg.from_user.username if msg.from_user else None,
                    "first_name": msg.from_user.first_name if msg.from_user else None,
                },
                "text": msg.text or "",
            }
        }
    return {}


async def _handle(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    controller: ControllerAgent,
) -> None:
    if not update.message:
        return

    raw_dict = _update_to_dict(update)
    incoming: IncomingMessage | None = _input_agent.process(raw_dict)

    if not incoming:
        return

    try:
        reply = await controller.handle(incoming)
        await update.message.reply_text(
            reply,
            parse_mode=ParseMode.MARKDOWN,
        )
    except Exception as exc:
        log.error("Handler error – user={} err={}", incoming.telegram_id, exc)
        await update.message.reply_text(
            "⚠️ Something went wrong. Please try again.",
        )


def register_handlers(app: Application, controller: ControllerAgent) -> None:
    COMMANDS = [
        "start", "add", "tasks", "done",
        "delay", "goal", "studyplan", "habits",
        "motivation", "help",
    ]

    def make_handler(cmd: str):
        async def _h(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
            await _handle(update, ctx, controller)
        return _h

    for cmd in COMMANDS:
        app.add_handler(CommandHandler(cmd, make_handler(cmd)))

    async def text_handler(update: Update, ctx: ContextTypes.DEFAULT_TYPE):
        await _handle(update, ctx, controller)

    app.add_handler(
        MessageHandler(filters.TEXT & ~filters.COMMAND, text_handler)
    )

    log.info("Telegram handlers registered – commands={}", COMMANDS)