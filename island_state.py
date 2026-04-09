"""
Локальное состояние интеграции с Островом: telegram_id → user_id, учёт отправленных отчётов за день.

Пока на backend нет daily_report_log и POST привязки — файл на диске; позже можно мигрировать на API.
"""
from __future__ import annotations

import json
import os
from datetime import date
from pathlib import Path
from typing import Any

_STATE_DIR = Path(__file__).resolve().parent / "data"
_MAPPING_FILE = _STATE_DIR / "island_telegram_user_map.json"
_REPORTS_FILE = _STATE_DIR / "island_daily_reports.json"


def _ensure_dir() -> None:
    _STATE_DIR.mkdir(parents=True, exist_ok=True)


def _load_json(path: Path) -> Any:
    if not path.is_file():
        return {}
    try:
        raw = path.read_text(encoding="utf-8")
        return json.loads(raw) if raw.strip() else {}
    except (OSError, json.JSONDecodeError):
        return {}


def _save_json(path: Path, data: Any) -> None:
    _ensure_dir()
    tmp = path.with_suffix(path.suffix + ".tmp")
    tmp.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
    tmp.replace(path)


def _parse_env_map() -> dict[int, int]:
    raw = (os.environ.get("ISLAND_TELEGRAM_USER_MAP") or "").strip()
    if not raw:
        return {}
    out: dict[int, int] = {}
    for part in raw.split(","):
        part = part.strip()
        if not part or ":" not in part:
            continue
        a, b = part.split(":", 1)
        try:
            out[int(a.strip())] = int(b.strip())
        except ValueError:
            continue
    return out


def load_telegram_user_map() -> dict[int, int]:
    """
    Слияние: дефолты из .env, поверх — файл (после /link и ручных правок).
    """
    m = _parse_env_map()
    file_data = _load_json(_MAPPING_FILE)
    if isinstance(file_data, dict):
        for k, v in file_data.items():
            try:
                m[int(k)] = int(v)
            except (TypeError, ValueError):
                continue
    return m


def set_telegram_user(telegram_id: int, user_id: int) -> None:
    data = _load_json(_MAPPING_FILE)
    if not isinstance(data, dict):
        data = {}
    data[str(int(telegram_id))] = int(user_id)
    _save_json(_MAPPING_FILE, data)


def report_key(telegram_id: int, d: date) -> str:
    return f"{int(telegram_id)}:{d.isoformat()}"


def is_day_report_sent(telegram_id: int, d: date) -> bool:
    data = _load_json(_REPORTS_FILE)
    if not isinstance(data, dict):
        return False
    return data.get(report_key(telegram_id, d)) is not None


def mark_day_report_sent(telegram_id: int, d: date, source: str) -> None:
    data = _load_json(_REPORTS_FILE)
    if not isinstance(data, dict):
        data = {}
    data[report_key(telegram_id, d)] = {"source": source}
    _save_json(_REPORTS_FILE, data)


def clear_day_report_for_test(telegram_id: int, d: date) -> None:
    """Для отладки: снять отметку за день."""
    data = _load_json(_REPORTS_FILE)
    if not isinstance(data, dict):
        return
    key = report_key(telegram_id, d)
    if key in data:
        del data[key]
        _save_json(_REPORTS_FILE, data)
