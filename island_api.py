"""
HTTP-клиент к API Острова (расписание, шаги, лог книг).
Базовый URL задаётся в .env целиком, включая префикс пути, если он есть.
"""
from __future__ import annotations

import logging
import os
from typing import Any

import aiohttp

logger = logging.getLogger("bridge")


def _base_url() -> str:
    return (os.environ.get("ISLAND_API_BASE_URL") or "").strip().rstrip("/")


def link_confirm_configured() -> bool:
    if (os.environ.get("ISLAND_LINK_CONFIRM_URL") or "").strip():
        return True
    base = _base_url()
    path = (os.environ.get("ISLAND_LINK_CONFIRM_PATH") or "").strip()
    return bool(base and path)


def _headers() -> dict[str, str]:
    key = (os.environ.get("ISLAND_API_KEY") or "").strip()
    if not key:
        return {}
    return {"X-Api-Key": key}


def _timeout() -> aiohttp.ClientTimeout:
    sec = float(os.environ.get("ISLAND_HTTP_TIMEOUT_SEC", "30") or "30")
    return aiohttp.ClientTimeout(total=sec)


async def get_schedule(
    session: aiohttp.ClientSession, user_id: int, date_from: str, date_to: str
) -> list[dict[str, Any]]:
    base = _base_url()
    if not base:
        return []
    params = {"user_id": user_id, "date_from": date_from, "date_to": date_to}
    url = f"{base}/schedule"
    try:
        async with session.get(url, params=params, headers=_headers(), timeout=_timeout()) as resp:
            if resp.status >= 400:
                text = await resp.text()
                logger.warning("Island GET /schedule %s: %s %s", resp.status, url, text[:500])
                return []
            data = await resp.json(content_type=None)
    except Exception:
        logger.exception("Island GET /schedule")
        return []
    return _extract_items(data)


def _extract_items(data: Any) -> list[dict[str, Any]]:
    if data is None:
        return []
    if isinstance(data, list):
        return [x for x in data if isinstance(x, dict)]
    if isinstance(data, dict):
        for key in ("items", "schedule", "data", "rows"):
            v = data.get(key)
            if isinstance(v, list):
                return [x for x in v if isinstance(x, dict)]
    return []


async def patch_step(
    session: aiohttp.ClientSession,
    dream_id: int,
    step_id: int,
    user_id: int,
    body: dict[str, Any],
) -> bool:
    base = _base_url()
    if not base:
        return False
    params = {"user_id": user_id}
    url = f"{base}/dreams/{dream_id}/steps/{step_id}"
    try:
        async with session.patch(
            url, params=params, json=body, headers=_headers(), timeout=_timeout()
        ) as resp:
            if resp.status >= 400:
                txt = await resp.text()
                logger.warning("Island PATCH step %s: %s %s", resp.status, url, txt[:500])
                return False
            return True
    except Exception:
        logger.exception("Island PATCH step")
        return False


async def post_book_log(
    session: aiohttp.ClientSession,
    dream_id: int,
    book_id: int,
    user_id: int,
    log_date: str,
    minutes_spent: int,
) -> bool:
    base = _base_url()
    if not base:
        return False
    params = {"user_id": user_id}
    url = f"{base}/dreams/{dream_id}/books/{book_id}/log"
    body = {"date": log_date, "minutes_spent": int(minutes_spent)}
    try:
        async with session.post(
            url, params=params, json=body, headers=_headers(), timeout=_timeout()
        ) as resp:
            if resp.status >= 400:
                txt = await resp.text()
                logger.warning("Island POST book log %s: %s %s", resp.status, url, txt[:500])
                return False
            return True
    except Exception:
        logger.exception("Island POST book log")
        return False


async def delete_book_log(
    session: aiohttp.ClientSession,
    dream_id: int,
    book_id: int,
    user_id: int,
    log_date: str,
) -> bool:
    base = _base_url()
    if not base:
        return False
    params = {"user_id": user_id, "date": log_date}
    url = f"{base}/dreams/{dream_id}/books/{book_id}/log"
    try:
        async with session.delete(url, params=params, headers=_headers(), timeout=_timeout()) as resp:
            if resp.status >= 400:
                txt = await resp.text()
                logger.warning("Island DELETE book log %s: %s %s", resp.status, url, txt[:500])
                return False
            return True
    except Exception:
        logger.exception("Island DELETE book log")
        return False


async def post_telegram_link_confirm(
    session: aiohttp.ClientSession, code: str, telegram_id: int
) -> tuple[bool, str]:
    """
    POST на ISLAND_LINK_CONFIRM_URL (полный URL) или base + ISLAND_LINK_CONFIRM_PATH.
    Возвращает (успех, текст ответа или ошибки).
    """
    full = (os.environ.get("ISLAND_LINK_CONFIRM_URL") or "").strip()
    path = (os.environ.get("ISLAND_LINK_CONFIRM_PATH") or "").strip()
    base = _base_url()
    if full:
        url = full
    elif base and path:
        url = f"{base}/{path.lstrip('/')}"
    else:
        return False, ""

    payload = {"code": code.strip(), "telegram_id": int(telegram_id)}
    try:
        async with session.post(
            url, json=payload, headers=_headers(), timeout=_timeout()
        ) as resp:
            txt = await resp.text()
            if resp.status >= 400:
                return False, txt[:800]
            return True, txt[:800]
    except Exception as e:
        logger.exception("Island POST link confirm")
        return False, str(e)
