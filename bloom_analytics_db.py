"""
Учёт личных обращений к боту (отдельная таблица, users не трогаем).
Тест 26.03: отчёты Максу по часам (Europe/Moscow).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from zoneinfo import ZoneInfo

MSK = ZoneInfo("Europe/Moscow")


def _strip_env(val: str | None) -> str:
    if val is None:
        return ""
    s = val.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s


def postgres_conninfo() -> str | None:
    from dream_db import postgres_conninfo as _ci

    return _ci()


def ensure_schema() -> None:
    import psycopg

    ci = postgres_conninfo()
    if not ci:
        return
    sql = """
    CREATE TABLE IF NOT EXISTS bloom_private_contacts (
        telegram_id BIGINT PRIMARY KEY,
        first_seen_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        last_message_at TIMESTAMPTZ NOT NULL DEFAULT NOW(),
        first_name TEXT,
        username TEXT
    );
    CREATE INDEX IF NOT EXISTS idx_bloom_pc_first_seen ON bloom_private_contacts (first_seen_at);
    """
    with psycopg.connect(ci) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql)


def upsert_contact(telegram_id: int, first_name: str | None, username: str | None) -> None:
    import psycopg

    ci = postgres_conninfo()
    if not ci:
        return
    fn = (first_name or "").strip() or None
    un = (username or "").strip() or None
    if un and not un.startswith("@"):
        un = "@" + un
    sql = """
        INSERT INTO bloom_private_contacts (telegram_id, first_seen_at, last_message_at, first_name, username)
        VALUES (%s, NOW(), NOW(), %s, %s)
        ON CONFLICT (telegram_id) DO UPDATE SET
            last_message_at = NOW(),
            first_name = COALESCE(EXCLUDED.first_name, bloom_private_contacts.first_name),
            username = COALESCE(EXCLUDED.username, bloom_private_contacts.username)
    """
    with psycopg.connect(ci) as conn:
        conn.autocommit = True
        with conn.cursor() as cur:
            cur.execute(sql, (telegram_id, fn, un))


@dataclass
class HourlyReport:
    day: date
    hour_window_label: str
    total_contacts_today: int
    new_in_previous_hour: int
    names_today: list[str]


def _parse_campaign_day() -> date:
    raw = (os.environ.get("BLOOM_CAMPAIGN_DATE") or "2026-03-26").strip()
    y, m, d = raw.split("-")
    return date(int(y), int(m), int(d))


def campaign_day() -> date:
    """День кампании (МСК, календарная дата)."""
    return _parse_campaign_day()


def fetch_hourly_report(
    now_msk: datetime,
    *,
    exclude_telegram_id: int | None = None,
) -> HourlyReport | None:
    """
    now_msk — момент срабатывания крона (например 08:00 МСК).
    «Прошедший час» — [now-1h, now).
    «За сегодня» — контакты с first_seen в этот календарный день по МСК.
    """
    import psycopg

    ci = postgres_conninfo()
    if not ci:
        return None

    day = _parse_campaign_day()
    if now_msk.date() != day:
        return None

    day_start = datetime(day.year, day.month, day.day, 0, 0, 0, tzinfo=MSK)
    day_end = day_start + timedelta(days=1)
    prev_end = now_msk.replace(minute=0, second=0, microsecond=0)
    prev_start = prev_end - timedelta(hours=1)

    excl = exclude_telegram_id

    with psycopg.connect(ci) as conn:
        with conn.cursor() as cur:
            if excl:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                      AND telegram_id <> %s
                    """,
                    (day_start, day_end, excl),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                    """,
                    (day_start, day_end),
                )
            total = cur.fetchone()[0]

            if excl:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                      AND telegram_id <> %s
                    """,
                    (prev_start, prev_end, excl),
                )
            else:
                cur.execute(
                    """
                    SELECT COUNT(*)::int FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                    """,
                    (prev_start, prev_end),
                )
            new_h = cur.fetchone()[0]

            if excl:
                cur.execute(
                    """
                    SELECT COALESCE(NULLIF(TRIM(first_name), ''), '—') AS fn
                    FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                      AND telegram_id <> %s
                    ORDER BY first_seen_at
                    """,
                    (day_start, day_end, excl),
                )
            else:
                cur.execute(
                    """
                    SELECT COALESCE(NULLIF(TRIM(first_name), ''), '—') AS fn
                    FROM bloom_private_contacts
                    WHERE first_seen_at >= %s AND first_seen_at < %s
                    ORDER BY first_seen_at
                    """,
                    (day_start, day_end),
                )
            names = [r[0] for r in cur.fetchall()]

    label = f"{prev_start.strftime('%H:%M')}–{prev_end.strftime('%H:%M')} МСК"
    return HourlyReport(
        day=day,
        hour_window_label=label,
        total_contacts_today=total,
        new_in_previous_hour=new_h,
        names_today=names,
    )


def format_hourly_report_text(rep: HourlyReport, *, admin_label: str = "Макс") -> str:
    names_block = "\n".join(f"• {n}" for n in rep.names_today) if rep.names_today else "—"
    return (
        f"📊 Bloom — отчёт за {rep.day.isoformat()} ({rep.hour_window_label})\n\n"
        f"Всего написало боту сегодня: {rep.total_contacts_today}\n"
        f"Новых за прошедший час: {rep.new_in_previous_hour}\n\n"
        f"Имена (first_name) всех, кто написал сегодня:\n{names_block}\n\n"
        f"— {admin_label}"
    )
