# ─────────────────────────────────────────────
#  Taskverse – Application Entry Point
# ─────────────────────────────────────────────
from __future__ import annotations

import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

os.makedirs("logs", exist_ok=True)

from backend.config import get_settings
from telegram_bot.bot import build_application
from utils.logger import log, setup_logger


def main() -> None:
    settings = get_settings()

    setup_logger()

    log.info("=" * 60)
    log.info("  🚀 Starting Taskverse AI Productivity System")
    log.info("  env={}  model={}", settings.app_env, settings.groq_model)
    log.info("=" * 60)

    # Validate required secrets
    missing = []
    if not settings.telegram_bot_token:
        missing.append("TELEGRAM_BOT_TOKEN")
    if not settings.groq_api_key:
        missing.append("GROQ_API_KEY")

    if missing:
        log.error("Missing required environment variables: {}", missing)
        log.error("Copy .env.example → .env and fill in the values")
        sys.exit(1)

    # Build app – run_polling() manages the event loop internally
    app = build_application()
    log.info("Taskverse bot is live – listening for messages…")
    app.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "edited_message"],
    )


if __name__ == "__main__":
    main()