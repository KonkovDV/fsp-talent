"""Outgoing email: console, file or SMTP (settings.MAIL_MODE)."""
from __future__ import annotations

import asyncio
import json
import logging
import smtplib
import ssl
import uuid
from datetime import UTC, datetime
from email.message import EmailMessage
from pathlib import Path

from app.core.config import settings

logger = logging.getLogger(__name__)


def _message(to: str, subject: str, text: str) -> EmailMessage:
    msg = EmailMessage()
    msg["From"] = settings.MAIL_FROM
    msg["To"] = to
    msg["Subject"] = subject
    msg.set_content(text)
    return msg


def _send_smtp(msg: EmailMessage) -> None:
    if settings.SMTP_SSL:
        server: smtplib.SMTP = smtplib.SMTP_SSL(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10,
                                                context=ssl.create_default_context())
    else:
        server = smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT, timeout=10)
    with server:
        if settings.SMTP_STARTTLS:
            server.starttls(context=ssl.create_default_context())
        if settings.SMTP_USER:
            server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
        server.send_message(msg)


def _write_file(to: str, subject: str, text: str, meta: dict) -> Path:
    folder = Path(settings.MAIL_FILE_DIR)
    folder.mkdir(parents=True, exist_ok=True)
    path = folder / f"{datetime.now(UTC):%Y%m%dT%H%M%S%f}-{uuid.uuid4().hex[:6]}.json"
    path.write_text(json.dumps({"to": to, "subject": subject, "text": text, **meta}, ensure_ascii=False),
                    encoding="utf-8")
    return path


async def send_mail(to: str, subject: str, text: str, meta: dict | None = None) -> None:
    """Deliver a letter. Failures are logged, not raised: the person can ask for the code again."""
    if to.strip().lower().endswith(".invalid"):
        return
    mode = settings.MAIL_MODE
    try:
        if mode == "smtp":
            await asyncio.to_thread(_send_smtp, _message(to, subject, text))
        elif mode == "file":
            await asyncio.to_thread(_write_file, to, subject, text, meta or {})
        else:
            logger.info("MAIL to=%s subject=%s\n%s", to, subject, text)
    except Exception:
        logger.exception("Mail delivery failed (mode=%s, to=%s)", mode, to)
