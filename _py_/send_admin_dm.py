#!/usr/bin/env python3
"""
Разовая отправка текста в личку владельцу бота (telegram_id из .env).
Бот может написать первым только если пользователь уже открывал чат с ботом (/start).
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from dotenv import load_dotenv
from aiogram import Bot

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")
ADMIN_ID = int(os.environ.get("ADMIN_TELEGRAM_ID") or os.environ.get("ADMIN_ID") or "0")

_DEFAULT = (
    "Макс, привет от Форжа. Мост на связи — двухполосный, шлюзы в норме. "
    "Если что, я на стороне кода."
)


async def _main() -> None:
    if not TELEGRAM_TOKEN or not ADMIN_ID:
        print("Нужны TELEGRAM_BOT_TOKEN и ADMIN_TELEGRAM_ID (или ADMIN_ID) в .env", file=sys.stderr)
        raise SystemExit(1)
    text = " ".join(sys.argv[1:]).strip() or _DEFAULT
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.send_message(ADMIN_ID, text)
        print("Сообщение отправлено в личку админу.")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_main())
