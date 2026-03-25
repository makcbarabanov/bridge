"""
Участники марафона: папки user_profiles/, логи dialogy/, идентификация по Telegram id / username.
Используется bridge_bot для персонального контекста и ответов Максу «по базе».
"""
from __future__ import annotations

import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent
USER_PROFILES = Path(os.environ.get("USER_PROFILES_DIR", _BASE / "user_profiles"))
DIALOGY = Path(os.environ.get("DIALOGY_DIR", _BASE / "dialogy"))

# id Telegram → папка в user_profiles/, как обращаться, подстроки для вопросов Максу «знаком ли ты…»
# Костя: в dialogy встречается как «Константин» — тот же id.
PARTICIPANTS: dict[int, dict] = {
    310055372: {
        "folder": "Макс",
        "call": "Макс",
        "aliases": ["макс", "максим", "барабанов", "makc"],
    },
    858036788: {
        "folder": "Костя_Захваткин",
        "call": "Костя",
        "aliases": ["костя", "костей", "костю", "константин", "захваткин", "кости"],
    },
    399807785: {
        "folder": "Света_Щербинина",
        "call": "Света",
        "aliases": ["света", "светлан", "щербинин", "светланы"],
    },
}

# Если id ещё не занесён в PARTICIPANTS, но username известен
USERNAME_TO_ID: dict[str, int] = {
    "svetashcherbinina": 399807785,
}


def resolve_participant(user) -> dict:
    """Собирает данные о текущем пользователе для промпта."""
    uid = user.id
    un = (user.username or "").lower()
    if uid in PARTICIPANTS:
        meta = {**PARTICIPANTS[uid], "id": uid, "resolved_by": "id"}
        return meta
    if un and un in USERNAME_TO_ID:
        rid = USERNAME_TO_ID[un]
        if rid in PARTICIPANTS:
            meta = {**PARTICIPANTS[rid], "id": rid, "resolved_by": "username"}
            return meta
    return {
        "folder": None,
        "call": (user.first_name or "друг").strip(),
        "aliases": [],
        "id": uid,
        "resolved_by": "fallback",
    }


def _read_trim(path: Path, max_chars: int) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) > max_chars:
        return text[: max_chars // 2] + "\n\n[… середина опущена …]\n\n" + text[-max_chars // 2 :]
    return text


def load_biography_primary(folder: str | None, max_chars: int = 4500) -> str:
    """Краткая справка — основной файл biography.txt (в промпт идёт в первую очередь)."""
    if not folder:
        return ""
    return _read_trim(USER_PROFILES / folder / "biography.txt", max_chars)


def load_biography_full_supplement(folder: str | None, max_chars: int = 10000) -> str:
    """Полная справка — biography_full.txt, если есть; дополнение к краткой."""
    if not folder:
        return ""
    p = USER_PROFILES / folder / "biography_full.txt"
    if not p.is_file():
        return ""
    return _read_trim(p, max_chars)


def load_dialogy_tail(telegram_id: int, max_chars: int = 7000) -> str:
    if not DIALOGY.is_dir():
        return ""
    for p in sorted(DIALOGY.glob(f"*_{telegram_id}.txt")):
        return _read_trim(p, max_chars)
    return ""


def build_interlocutor_block(user, admin_id: int) -> str:
    """Кто сейчас пишет + справка + хвост dialogy."""
    info = resolve_participant(user)
    pid = info["id"]
    call = info["call"]
    lines = [
        "=== Текущий собеседник (Telegram) ===",
        f"telegram_id: {pid}",
        f"Обращайся по имени: **{call}** (не выдумывай другое имя).",
    ]
    if user.username:
        lines.append(f"username: @{user.username}")
    if user.first_name or user.last_name:
        lines.append(
            f"имя в профиле: {(user.first_name or '')} {(user.last_name or '')}".strip()
        )
    lines.append(
        f"Владелец бота — **Макс** (telegram_id {admin_id}). "
        f"Если текущий telegram_id не равен {admin_id}, это **не Макс**. "
        f"Не называй собеседника Максом и не приписывай ему роль Макса."
    )
    folder = info.get("folder")
    if folder:
        bio = load_biography_primary(folder)
        if bio.strip():
            lines.append("")
            lines.append(
                f"=== Краткая справка о человеке (основа: user_profiles/{folder}/biography.txt) ==="
            )
            lines.append(bio)
    dlg = load_dialogy_tail(pid)
    if dlg.strip():
        lines.append("")
        lines.append("=== Недавний диалог с этим человеком (сервер: dialogy) ===")
        lines.append(dlg)
    return "\n".join(lines)


def knowledge_lookup_for_admin(text: str, asker_id: int, admin_id: int) -> str:
    """
    Если Макс спрашивает, знаком ли Bloom с Костей / Светой / … — подставляем файлы с сервера.
    """
    if asker_id != admin_id:
        return ""
    tl = text.lower()
    triggers = (
        "знаком",
        "знаешь",
        "знаете",
        "знал",
        "знала",
        "кто такой",
        "кто такая",
        "кто такие",
        "расскажи про",
        "расскажи что",
        "расскажи как",
        "что знаешь",
        "что скажешь",
        "что известно",
        "что у него",
        "что у неё",
        "чем жив",
        "как дела у",
        "как он",
        "как она",
        "виделись",
        "встречались",
        "вспомни",
        "напомни",
        "помнишь",
        "помнишь ли",
        "опиши",
        "характеристик",
        "биограф",
        "досье",
        "информация о",
        "есть инфа",
        "есть данные",
        "загляни в",
        "по файлу",
        "в файле",
        "на сервере",
        "про человека",
        "этот человек",
        "человек из",
    )
    if not any(t in tl for t in triggers):
        return ""
    blocks: list[str] = []
    for pid, meta in PARTICIPANTS.items():
        if pid == admin_id:
            continue
        hit = False
        for a in meta.get("aliases", []):
            if len(a) >= 3 and a in tl:
                hit = True
                break
        if not hit:
            continue
        folder = meta["folder"]
        call = meta["call"]
        bio_short = load_biography_primary(folder, max_chars=6000)
        bio_full = load_biography_full_supplement(folder, max_chars=12000)
        dlg = load_dialogy_tail(pid, max_chars=9000)
        part = [
            f"=== СЛУЖЕБНЫЕ ДАННЫЕ: участник «{call}» (telegram_id {pid}) ===",
            "(Ниже — то, что хранится на сервере; опирайся на это, не выдумывай факты.)",
        ]
        if bio_short.strip():
            part.append("--- Краткая справка (biography.txt) — основа ---")
            part.append(bio_short)
        if bio_full.strip():
            part.append("--- Полная справка (biography_full.txt) — дополнительно, фрагмент ---")
            part.append(bio_full)
        if dlg.strip():
            part.append("--- dialogy (хвост) ---")
            part.append(dlg)
        blocks.append("\n".join(part))
    return "\n\n".join(blocks) if blocks else ""
