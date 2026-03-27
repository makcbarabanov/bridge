#!/usr/bin/env python3
"""
Разовая миграция: dialogy/*.txt + user_profiles/*/dialog_with_bloom.txt + chat_history.txt
→ единый user_profiles/<папка>/chat_history.txt; удаление dialog_with_bloom и dialogy.

Запуск из корня: python _py_/migrate_dialogy_to_chat_history.py
"""
from __future__ import annotations

import sys
from pathlib import Path

_BASE = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(_BASE))

from bridge_participants import PARTICIPANTS, USER_PROFILES  # noqa: E402

# Старая папка (может отсутствовать после миграции).
DIALOGY = _BASE / "dialogy"

LEGACY_NAME = "dialog_with_bloom.txt"
CHAT_NAME = "chat_history.txt"


def _read(p: Path) -> str:
    if not p.is_file():
        return ""
    return p.read_text(encoding="utf-8", errors="replace")


def _is_placeholder_chat(text: str) -> bool:
    t = text.strip()
    if not t:
        return True
    lines = [ln for ln in t.splitlines() if ln.strip() and not ln.strip().startswith("#")]
    return len(lines) == 0


def merge_texts(legacy_dialogy: str, dialog_with_bloom: str, old_chat: str) -> str:
    """Собираем один лог: приоритет у полного dialog_with_bloom, иначе склейка."""
    dwb = dialog_with_bloom.strip()
    leg = legacy_dialogy.strip()
    ch = old_chat.strip()

    if dwb and leg:
        if leg in dwb or dwb.startswith(leg[: min(500, len(leg))]):
            base = dwb
        elif dwb in leg:
            base = leg
        else:
            base = (
                leg
                + "\n\n---\n\n=== продолжение ("
                + LEGACY_NAME
                + ") ===\n\n"
                + dwb
            )
    elif dwb:
        base = dwb
    elif leg:
        base = leg
    else:
        base = ""

    if ch and not _is_placeholder_chat(ch):
        if ch not in base:
            base = (base + "\n\n---\n\n=== ранее в chat_history.txt ===\n\n" + ch).strip()

    return base if base else ""


def migrate_participants() -> None:
    id_to_folder = {uid: meta["folder"] for uid, meta in PARTICIPANTS.items()}
    for uid, folder in id_to_folder.items():
        target_dir = USER_PROFILES / folder
        target_dir.mkdir(parents=True, exist_ok=True)
        leg_files = list(DIALOGY.glob(f"*_{uid}.txt"))
        legacy_txt = _read(leg_files[0]) if leg_files else ""
        dwb_txt = _read(target_dir / LEGACY_NAME)
        ch_txt = _read(target_dir / CHAT_NAME)
        merged = merge_texts(legacy_txt, dwb_txt, ch_txt)
        if not merged:
            print(f"[skip empty] participant {uid} → {folder}")
            continue
        out = target_dir / CHAT_NAME
        out.write_text(merged + ("\n" if not merged.endswith("\n") else ""), encoding="utf-8")
        print(f"[ok] {folder} → {CHAT_NAME} ({len(merged)} chars)")
        leg = target_dir / LEGACY_NAME
        if leg.is_file():
            leg.unlink()
            print(f"     removed {LEGACY_NAME}")


def migrate_guest_dialogy_files() -> None:
    """Файлы в dialogy, не покрытые участниками: папка = stem имени файла."""
    participant_ids = set(PARTICIPANTS.keys())
    for f in sorted(DIALOGY.glob("*.txt")):
        stem = f.stem
        part = stem.rsplit("_", 1)
        if len(part) < 2:
            continue
        try:
            uid = int(part[-1])
        except ValueError:
            print(f"[skip bad name] {f.name}")
            continue
        if uid in participant_ids:
            continue
        dest_dir = USER_PROFILES / stem
        dest_dir.mkdir(parents=True, exist_ok=True)
        text = _read(f)
        out = dest_dir / CHAT_NAME
        old = _read(out)
        if old.strip() and not _is_placeholder_chat(old):
            merged = merge_texts(text, "", old)
        else:
            merged = text
        if merged:
            out.write_text(merged + ("\n" if not merged.endswith("\n") else ""), encoding="utf-8")
            print(f"[ok guest] {stem}/ {CHAT_NAME}")


def main() -> None:
    if not DIALOGY.is_dir():
        print("Нет папки dialogy — пропуск миграции из dialogy.")
    migrate_participants()
    migrate_guest_dialogy_files()
    print("Готово. Проверьте user_profiles/*/chat_history.txt и удалите dialogy/ вручную, если нужно.")


if __name__ == "__main__":
    main()
