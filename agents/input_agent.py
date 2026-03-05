# ─────────────────────────────────────────────
#  Taskverse – Input Agent
# ─────────────────────────────────────────────
"""
Receives raw Telegram messages, normalises them,
and forwards a structured payload to the Controller Agent.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from utils.helpers import sanitise_text
from utils.logger import log


@dataclass
class IncomingMessage:
    """Normalised message payload passed downstream."""
    telegram_id: int
    username: Optional[str]
    first_name: Optional[str]
    raw_text: str
    command: Optional[str] = None          # e.g. "add", "tasks", "goal"
    command_args: str = ""                 # text after the command
    extra: Dict[str, Any] = field(default_factory=dict)


class InputAgent:
    """
    Responsibility
    ──────────────
    1. Accept a raw Telegram Update payload.
    2. Extract user metadata and message text.
    3. Parse Telegram slash-commands.
    4. Return a clean IncomingMessage for the Controller.
    """

    KNOWN_COMMANDS = {
        "start", "add", "tasks", "done",
        "delay", "goal", "studyplan", "habits",
        "help", "motivation",
    }

    def process(self, update: Dict[str, Any]) -> Optional[IncomingMessage]:
        """
        Parse a Telegram Update dict into an IncomingMessage.

        Returns None if the update contains no usable message.
        """
        try:
            message = update.get("message") or update.get("edited_message")
            if not message:
                log.debug("InputAgent: no message in update, skipping")
                return None

            user = message.get("from", {})
            telegram_id: int = user.get("id", 0)
            if not telegram_id:
                log.warning("InputAgent: could not extract telegram_id")
                return None

            raw_text: str = sanitise_text(message.get("text", ""))
            if not raw_text:
                log.debug("InputAgent: empty text, skipping")
                return None

            command, command_args = self._parse_command(raw_text)

            incoming = IncomingMessage(
                telegram_id=telegram_id,
                username=user.get("username"),
                first_name=user.get("first_name"),
                raw_text=raw_text,
                command=command,
                command_args=command_args,
            )

            log.info(
                "InputAgent processed – user={} command={} text={!r}",
                telegram_id,
                command,
                raw_text[:80],
            )
            return incoming

        except Exception as exc:
            log.error("InputAgent.process error: {}", exc)
            return None

    def _parse_command(self, text: str) -> tuple[Optional[str], str]:
        """
        Extract slash-command and trailing arguments.

        '/add Finish backend tomorrow' → ('add', 'Finish backend tomorrow')
        'Just a normal message'        → (None, 'Just a normal message')
        """
        if not text.startswith("/"):
            return None, text

        parts = text.lstrip("/").split(maxsplit=1)
        # Strip @BotUsername suffix (e.g. /add@TaskverseBot)
        cmd = parts[0].split("@")[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd not in self.KNOWN_COMMANDS:
            log.debug("InputAgent: unrecognised command={}", cmd)
            return cmd, args  # still pass through so controller can handle

        return cmd, args
