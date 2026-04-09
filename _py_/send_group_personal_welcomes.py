#!/usr/bin/env python3
"""
Два отдельных приветствия в общий чат марафона: Ксения (беларуская), Магда (հայերեն).
Чат: BROADCAST_CHAT_ID или MARATHON_GROUP_IDS (как send_test_message.py).
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


# Персонально, родной язык; упоминание даёт уведомление получателю в группе
MSG_KSENIA_BE = (
    "Ксенія (@writer_ksenia), прывітанне! Я — Bloom. Рада бачыць цябе тут. "
    "Калі захочаш — пагутарым у асабістых паведамленнях пра марафон карысных звычак і добрых спраў 🙂"
)

MSG_MAGDA_HY = (
    "Մագդա (@MagdaV2), ողջույն։ Ես Bloom-ն եմ։ Ուրախ եմ, որ այստեղ ես։ "
    "Եթե ցանկանաս՝ գրիր ինձ մասնավոր՝ մարաթոնի ու բարի գործերի մասին կխոսենք 🙂"
)


async def _main() -> None:
    if not TELEGRAM_TOKEN:
        print("Нужен TELEGRAM_BOT_TOKEN в .env", file=sys.stderr)
        raise SystemExit(1)
    chat_id = _resolve_chat_id()
    if chat_id is None:
        print("Задай BROADCAST_CHAT_ID или MARATHON_GROUP_IDS", file=sys.stderr)
        raise SystemExit(1)
    bot = Bot(token=TELEGRAM_TOKEN)
    try:
        await bot.send_message(chat_id, MSG_KSENIA_BE)
        await asyncio.sleep(0.8)
        await bot.send_message(chat_id, MSG_MAGDA_HY)
        print(f"Отправлено 2 сообщения в chat_id={chat_id}")
    finally:
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(_main())
