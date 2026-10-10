"""Second factor for the moderation desk: RFC 6238 TOTP (HMAC-SHA1, 6 digits, 30 s).

Enrollment is a console command on the server, so a stolen password cannot turn the factor on or off:

    python -m app.services.totp enroll hr@sibcode.demo
    python -m app.services.totp disable hr@sibcode.demo

The secret is stored sealed with AES-GCM (services/field_cipher.py). A code is accepted once:
a step at or below the last accepted one is a replay.
"""
import argparse
import asyncio
import base64
import hashlib
import hmac
import os
import struct
from datetime import UTC, datetime, timedelta
from urllib.parse import quote

from app.services.field_cipher import open_seal, seal

STEP_SECONDS = 30
DIGITS = 6
DRIFT_STEPS = 1
UNLOCK = timedelta(minutes=15)
ISSUER = "ФСП Талант"


def new_secret() -> str:
    return base64.b32encode(os.urandom(20)).decode("ascii")


def _key(secret: str) -> bytes:
    clean = secret.replace(" ", "").upper()
    return base64.b32decode(clean + "=" * (-len(clean) % 8))


def hotp(secret: str, counter: int) -> str:
    digest = hmac.new(_key(secret), struct.pack(">Q", counter), hashlib.sha1).digest()
    offset = digest[-1] & 0x0F
    value = struct.unpack(">I", digest[offset:offset + 4])[0] & 0x7FFFFFFF
    return str(value % 10 ** DIGITS).zfill(DIGITS)


def step_at(moment: datetime) -> int:
    return int(moment.timestamp()) // STEP_SECONDS


def accept(secret: str, code: str, moment: datetime, last_step: int | None) -> int | None:
    """The matched step, or None. One step of clock drift either way is allowed."""
    code = (code or "").strip().replace(" ", "")
    if len(code) != DIGITS or not code.isdigit():
        return None
    now = step_at(moment)
    for step in range(now - DRIFT_STEPS, now + DRIFT_STEPS + 1):
        if last_step is not None and step <= last_step:
            continue
        if hmac.compare_digest(hotp(secret, step), code):
            return step
    return None


def provisioning_uri(secret: str, account: str) -> str:
    label = quote(f"{ISSUER}:{account}")
    return (f"otpauth://totp/{label}?secret={secret}&issuer={quote(ISSUER)}"
            f"&algorithm=SHA1&digits={DIGITS}&period={STEP_SECONDS}")


def seal_secret(employer_id: str, secret: str) -> str:
    return seal(employer_id, "employers", "totp_secret", secret)


def open_secret(employer_id: str, stored: str) -> str:
    return open_seal(employer_id, "employers", "totp_secret", stored)


def unlocked(verified_at: datetime | None, moment: datetime) -> bool:
    return verified_at is not None and moment - verified_at < UNLOCK


async def _employer(db, email: str):
    from sqlalchemy import select

    from app.models import Employer
    from app.services.field_cipher import email_is
    return await db.scalar(select(Employer).where(email_is(Employer, email)))


async def enroll(email: str, read_code=input) -> bool:
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls

    bypass_rls()
    async with AsyncSessionLocal() as db:
        employer = await _employer(db, email)
        if employer is None:
            print(f"Компании с почтой {email} нет")
            return False
        secret = new_secret()
        print("Ключ для приложения-аутентификатора:", secret)
        print("Ссылка для QR:", provisioning_uri(secret, email))
        try:
            code = read_code("Код из приложения: ")
        except EOFError:
            code = ""
        step = accept(secret, code, datetime.now(UTC), None)
        if step is None:
            print("Код не подошёл, второй фактор не включён")
            return False
        employer.totp_secret = seal_secret(str(employer.id), secret)
        employer.totp_last_step = step
        employer.totp_verified_at = None
        await db.commit()
        print("Второй фактор включён: стол модерации теперь спрашивает код")
        return True


async def disable(email: str) -> bool:
    from app.core.database import AsyncSessionLocal
    from app.core.rls import bypass_rls

    bypass_rls()
    async with AsyncSessionLocal() as db:
        employer = await _employer(db, email)
        if employer is None or employer.totp_secret is None:
            print(f"У {email} второй фактор не включён")
            return False
        employer.totp_secret = employer.totp_last_step = employer.totp_verified_at = None
        await db.commit()
        print("Второй фактор выключен")
        return True


def main() -> None:
    parser = argparse.ArgumentParser(description="Второй фактор (TOTP) для стола модерации")
    parser.add_argument("command", choices=("enroll", "disable"))
    parser.add_argument("email")
    args = parser.parse_args()
    done = asyncio.run(enroll(args.email) if args.command == "enroll" else disable(args.email))
    raise SystemExit(0 if done else 1)


if __name__ == "__main__":
    main()
