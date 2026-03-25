"""
Статистика мечт из PostgreSQL (таблицы users / dreams / dreams_statuses).
"""
from __future__ import annotations

import os
from typing import NamedTuple


class DreamStats(NamedTuple):
    first_name: str
    total: int
    in_progress: int


def _strip_env(val: str | None) -> str:
    if val is None:
        return ""
    s = val.strip()
    if len(s) >= 2 and s[0] == s[-1] and s[0] in "\"'":
        s = s[1:-1]
    return s


def postgres_conninfo() -> str | None:
    host = _strip_env(os.environ.get("POSTGRES_HOST"))
    port = _strip_env(os.environ.get("POSTGRES_PORT")) or "5432"
    user = _strip_env(os.environ.get("POSTGRES_USER"))
    password = _strip_env(os.environ.get("POSTGRES_PASSWORD"))
    dbname = _strip_env(os.environ.get("POSTGRES_DB"))
    if not all([host, user, password, dbname]):
        return None
    return (
        f"host={host} port={port} user={user} password={password} "
        f"dbname={dbname} connect_timeout=12 sslmode=prefer"
    )


def fetch_dream_stats_for_telegram(telegram_id: int) -> DreamStats | None:
    """Количество мечт и «в работе» для пользователя по telegram_id."""
    try:
        import psycopg
    except ImportError:
        return None

    ci = postgres_conninfo()
    if not ci:
        return None

    sql = """
        SELECT COALESCE(NULLIF(TRIM(u.name), ''), 'друг') AS fn,
               (SELECT COUNT(*)::int FROM dreams d WHERE d.user_id = u.id) AS total,
               (SELECT COUNT(*)::int FROM dreams d
                WHERE d.user_id = u.id
                  AND d.status_id = (SELECT id FROM dreams_statuses WHERE code = 'in_progress' LIMIT 1)
               ) AS in_progress
        FROM users u
        WHERE u.telegram_id = %s
        LIMIT 1
    """
    try:
        with psycopg.connect(ci) as conn:
            with conn.cursor() as cur:
                cur.execute(sql, (telegram_id,))
                row = cur.fetchone()
                if not row:
                    return None
                return DreamStats(first_name=row[0], total=int(row[1]), in_progress=int(row[2]))
    except Exception:
        raise
