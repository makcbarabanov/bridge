#!/usr/bin/env python3
"""
Отправка тестового сообщения в указанный чат (группа/супергруппа или личка по id).
Чат: BROADCAST_CHAT_ID в .env или первый id из MARATHON_GROUP_IDS.
Текст: аргументы командной строки или по умолчанию «всем привет».

Пример: python _py_/send_test_message.py Всем привет с моста
"""
from __future__ import annotations

import asyncio
import os
import sys
from pathlib import Path

from aiogram import Bot
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

TELEGRAM_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN")


def _resolve_chat_id() -> int | None:
    raw = (os.environ.get("BROADCAST_CHAT_ID") or "").strip()
    if raw:
        try:
            return int(raw)
        except ValueError:
            pass
    for part in (os.environ.get("MARATHON_GROUP_IDS") or "").split(","):
        part = part.strip()
        if not part:
            continue
        try:
            return int(part)
        except ValueError:
            continue
    return None


async def _main() -> None:
    if not TELEGRAM_TOKEN:
        print("Нужен TELEGRAM_BOT_TOKEN в .env", file=sys.stderr)
        raise SystemExit(1)
    chat_id = _resolve_chat_id()
    if chat_id is None:
        print(
            "Задай в .env BROADCAST_CHAT_ID (число) или MARATHON_GROUP_IDS с id группы.",
            file=sys.stderr,
        )
        raise SystemExit(1)
    text = " ".join(sys.argv[1:]).strip() or "всем привет"
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.send_message(chat_id, text)
        print(f"Отправлено в chat_id={chat_id}: {text!r}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_main())
