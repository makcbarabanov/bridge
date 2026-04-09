"""
Утро/вечер: расписание Острова в личку Telegram. Локальный учёт «день уже отчитан» до появления daily_report_log на backend.
"""
from __future__ import annotations

import logging
import os
from datetime import date, datetime
from typing import Any
from zoneinfo import ZoneInfo

import aiohttp
from aiogram import Bot
from aiogram.types import InlineKeyboardButton, InlineKeyboardMarkup

import island_api
import island_state

logger = logging.getLogger("bridge")


def _tz() -> ZoneInfo:
    name = (os.environ.get("ISLAND_TIMEZONE") or "Europe/Moscow").strip()
    try:
        return ZoneInfo(name)
    except Exception:
        return ZoneInfo("Europe/Moscow")


def get_schedule_timezone() -> ZoneInfo:
    """Часовой пояс для крона утра/вечера и даты «сегодня»."""
    return _tz()


def _today_iso() -> str:
    return datetime.now(_tz()).date().isoformat()


def today_iso() -> str:
    """Сегодняшняя дата (локальный TZ из ISLAND_TIMEZONE) в формате YYYY-MM-DD."""
    return _today_iso()


def _normalize_item_date(raw: Any) -> str | None:
    if raw is None:
        return None
    if isinstance(raw, str):
        return raw[:10] if len(raw) >= 10 else raw
    if isinstance(raw, datetime):
        return raw.date().isoformat()
    return None


def items_for_date(items: list[dict[str, Any]], day_iso: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for it in items:
        d = _normalize_item_date(it.get("date"))
        if d == day_iso:
            st = (it.get("source_type") or "").strip().lower()
            if st not in ("step", "book"):
                logger.info("Island: пропуск неизвестного source_type=%r", it.get("source_type"))
                continue
            out.append(it)
    return out


def stats_for_day(items: list[dict[str, Any]], day_iso: str) -> tuple[list[dict], list[dict], list[dict]]:
    """todo, done, all (only today)"""
    today_items = items_for_date(items, day_iso)
    done = [x for x in today_items if x.get("completed") is True]
    todo = [x for x in today_items if x.get("completed") is not True]
    return todo, done, today_items


def _title(it: dict[str, Any]) -> str:
    t = it.get("title")
    return str(t).strip() if t is not None else "—"


def format_morning_message(items: list[dict[str, Any]], day_iso: str) -> str:
    _, _, all_today = stats_for_day(items, day_iso)
    if not all_today:
        return "На сегодня в расписании пусто — запланировано 0 дел. Отдыхай по-братски."

    lines = ["🌿 План на сегодня (Остров):", ""]
    todo, done, _ = stats_for_day(items, day_iso)
    if todo:
        lines.append("Сделать:")
        for i, it in enumerate(todo, 1):
            lines.append(f"{i}. {_title(it)}")
        lines.append("")
    if done:
        lines.append("Уже закрыто:")
        for i, it in enumerate(done, 1):
            lines.append(f"· {_title(it)}")
    return "\n".join(lines).strip()


def format_evening_summary(items: list[dict[str, Any]], day_iso: str) -> str:
    _, _, all_today = stats_for_day(items, day_iso)
    n = len(all_today)
    if n == 0:
        return "Запланировано 0 дел. Отдыхай по-братски."

    _, done, _ = stats_for_day(items, day_iso)
    dcnt = len(done)
    pct = int(round(100.0 * dcnt / n)) if n else 0
    return (
        f"Выполнено {dcnt} из {n} запланированных дел, это {pct}%.\n"
        f"Ниже кнопка «Подробнее» — список дел и статусы."
    )


def format_detail_lines(items: list[dict[str, Any]], day_iso: str) -> str:
    _, _, all_today = stats_for_day(items, day_iso)
    if not all_today:
        return "Список пуст."

    lines: list[str] = []
    for i, it in enumerate(all_today, 1):
        ok = it.get("completed") is True
        mark = "+" if ok else "−"
        lines.append(f"{i}. {_title(it)} {mark}")
    return "\n".join(lines)


def evening_keyboard(day_iso: str) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text="Подробнее", callback_data=f"island:d:{day_iso}")]
        ]
    )


def _cb_action(action: str, source_type: str, dream_id: int, source_id: int, day_iso: str) -> str:
    return f"island:a:{action}:{source_type}:{dream_id}:{source_id}:{day_iso}"


def day_actions_keyboard(items: list[dict[str, Any]], day_iso: str) -> InlineKeyboardMarkup:
    """
    Кнопки под списком дел:
    - N ✅ (сделал)
    - N ❌ (не сделал)
    """
    _, _, all_today = stats_for_day(items, day_iso)
    rows: list[list[InlineKeyboardButton]] = []
    for i, it in enumerate(all_today, 1):
        st = str(it.get("source_type") or "").strip().lower()
        try:
            dream_id = int(it.get("dream_id"))
            source_id = int(it.get("source_id"))
        except (TypeError, ValueError):
            continue
        if st not in ("step", "book"):
            continue
        rows.append(
            [
                InlineKeyboardButton(
                    text=f"{i} ✅",
                    callback_data=_cb_action("d", st, dream_id, source_id, day_iso),
                ),
                InlineKeyboardButton(
                    text=f"{i} ❌",
                    callback_data=_cb_action("u", st, dream_id, source_id, day_iso),
                ),
            ]
        )
    return InlineKeyboardMarkup(inline_keyboard=rows or [[InlineKeyboardButton(text="Нет действий", callback_data="island:noop")]])


async def _send_evening_report(
    bot: Bot, telegram_id: int, user_id: int, day_iso: str, source: str
) -> None:
    if island_state.is_day_report_sent(telegram_id, date.fromisoformat(day_iso)):
        return

    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)

    text = format_evening_summary(items, day_iso)
    await bot.send_message(
        telegram_id,
        text,
        reply_markup=evening_keyboard(day_iso),
    )
    island_state.mark_day_report_sent(telegram_id, date.fromisoformat(day_iso), source)
    logger.info("Island: вечерний отчёт отправлен tg=%s user_id=%s %s", telegram_id, user_id, source)


async def _send_morning_plan(bot: Bot, telegram_id: int, user_id: int, day_iso: str) -> None:
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    text = format_morning_message(items, day_iso)
    await bot.send_message(telegram_id, text)


async def island_morning_job(bot: Bot) -> None:
    if not (os.environ.get("ISLAND_API_BASE_URL") or "").strip():
        return
    if os.environ.get("ISLAND_SCHEDULE_ENABLED", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    day_iso = _today_iso()
    mapping = island_state.load_telegram_user_map()
    if not mapping:
        logger.debug("Island: утро — нет привязок telegram→user, пропуск")
        return
    for tg_id, uid in sorted(mapping.items()):
        try:
            await _send_morning_plan(bot, tg_id, uid, day_iso)
        except Exception:
            logger.exception("Island: утро tg=%s", tg_id)


async def island_evening_job(bot: Bot) -> None:
    if not (os.environ.get("ISLAND_API_BASE_URL") or "").strip():
        return
    if os.environ.get("ISLAND_SCHEDULE_ENABLED", "").strip().lower() not in (
        "1",
        "true",
        "yes",
    ):
        return
    day_iso = _today_iso()
    mapping = island_state.load_telegram_user_map()
    if not mapping:
        return
    for tg_id, uid in sorted(mapping.items()):
        try:
            if island_state.is_day_report_sent(tg_id, date.fromisoformat(day_iso)):
                continue
            await _send_evening_report(bot, tg_id, uid, day_iso, "cron")
        except Exception:
            logger.exception("Island: вечер tg=%s", tg_id)


async def send_manual_day_report(bot: Bot, telegram_id: int, user_id: int) -> str:
    """Вызывается из /report — всегда шлёт отчёт и помечает день (перезапись source=manual)."""
    day_iso = _today_iso()
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    text = format_evening_summary(items, day_iso)
    await bot.send_message(
        telegram_id,
        text,
        reply_markup=evening_keyboard(day_iso),
    )
    island_state.mark_day_report_sent(telegram_id, date.fromisoformat(day_iso), "manual")
    return text


async def detail_text_for_callback(user_id: int, day_iso: str) -> str:
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    body = format_detail_lines(items, day_iso)
    return "Дела за день:\n\n" + body


async def send_manual_morning(bot: Bot, telegram_id: int, user_id: int) -> None:
    day_iso = _today_iso()
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    await bot.send_message(telegram_id, format_morning_message(items, day_iso))


async def send_manual_evening(bot: Bot, telegram_id: int, user_id: int) -> None:
    day_iso = _today_iso()
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    await bot.send_message(
        telegram_id,
        format_evening_summary(items, day_iso),
        reply_markup=evening_keyboard(day_iso),
    )


async def detail_with_actions(user_id: int, day_iso: str) -> tuple[str, InlineKeyboardMarkup]:
    async with aiohttp.ClientSession() as session:
        items = await island_api.get_schedule(session, user_id, day_iso, day_iso)
    body = format_detail_lines(items, day_iso)
    kb = day_actions_keyboard(items, day_iso)
    return "Дела за день:\n\n" + body, kb


async def apply_item_action(
    user_id: int,
    action: str,  # d=done, u=undone
    source_type: str,
    dream_id: int,
    source_id: int,
    day_iso: str,
) -> tuple[bool, str]:
    st = (source_type or "").strip().lower()
    if st not in ("step", "book"):
        return False, "Неизвестный тип пункта."

    async with aiohttp.ClientSession() as session:
        if st == "step":
            ok = await island_api.patch_step(
                session=session,
                dream_id=dream_id,
                step_id=source_id,
                user_id=user_id,
                body={"completed": action == "d"},
            )
            if ok:
                return True, "Шаг обновлён."
            return False, "Не удалось обновить шаг."

        if action == "d":
            ok = await island_api.post_book_log(
                session=session,
                dream_id=dream_id,
                book_id=source_id,
                user_id=user_id,
                log_date=day_iso,
                minutes_spent=int(os.environ.get("ISLAND_BOOK_LOG_MINUTES", "15") or "15"),
            )
            if ok:
                return True, "Книга отмечена как выполненная."
            return False, "Не удалось записать лог книги."

        ok = await island_api.delete_book_log(
            session=session,
            dream_id=dream_id,
            book_id=source_id,
            user_id=user_id,
            log_date=day_iso,
        )
        if ok:
            return True, "Отметка по книге снята."
        return False, "Не удалось снять отметку по книге."
