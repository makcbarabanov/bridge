"""
Участники марафона: папки user_profiles/
(biography.txt, chat_history.txt, bloom_traits.txt).
Гости без записи в PARTICIPANTS — user_profiles/<имя>_<id>/.
"""
from __future__ import annotations

import os
from pathlib import Path

_BASE = Path(__file__).resolve().parent
USER_PROFILES = Path(os.environ.get("USER_PROFILES_DIR", _BASE / "user_profiles"))

# Единый автолог переписки с ботом в папке пользователя (см. README.md в корне проекта).
DIALOG_LOG_FILENAME = "chat_history.txt"
# Наблюдения Блума о человеке (ключевые черты, сложности, чем помочь).
TRAITS_FILENAME = "bloom_traits.txt"

# id Telegram → папка в user_profiles/, как обращаться, подстроки для вопросов Максу «знаком ли ты…»
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
    1461824816: {
        "folder": "Ксения_Роговенко",
        "call": "Ксения",
        "aliases": [
            "ксения",
            "ксюша",
            "ксен",
            "роговенко",
            "writer_ksenia",
            "книгиня",
        ],
    },
}

# Если id ещё не занесён в PARTICIPANTS, но username известен
USERNAME_TO_ID: dict[str, int] = {
    "svetashcherbinina": 399807785,
    "writer_ksenia": 1461824816,
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


def load_bloom_traits(telegram_id: int, max_chars: int = 2800) -> str:
    """Хвост bloom_traits.txt для промпта (участник или гость)."""
    folder = _participant_folder_for_id(telegram_id)
    if folder:
        p = USER_PROFILES / folder / TRAITS_FILENAME
        if p.is_file():
            return _read_trim(p, max_chars)
        return ""
    if not USER_PROFILES.is_dir():
        return ""
    for d in sorted(USER_PROFILES.glob(f"*_{telegram_id}")):
        if not d.is_dir():
            continue
        p = d / TRAITS_FILENAME
        if p.is_file():
            return _read_trim(p, max_chars)
    return ""


def load_biography_full_supplement(folder: str | None, max_chars: int = 10000) -> str:
    """Полная справка — biography_full.txt, если есть; дополнение к краткой."""
    if not folder:
        return ""
    p = USER_PROFILES / folder / "biography_full.txt"
    if not p.is_file():
        return ""
    return _read_trim(p, max_chars)


def _participant_folder_for_id(telegram_id: int) -> str | None:
    meta = PARTICIPANTS.get(telegram_id)
    if meta:
        return meta.get("folder")
    return None


def load_chat_history_tail(telegram_id: int, max_chars: int = 7000) -> str:
    """Хвост файла chat_history.txt для промпта (участник или гость)."""
    folder = _participant_folder_for_id(telegram_id)
    if folder:
        p = USER_PROFILES / folder / DIALOG_LOG_FILENAME
        if p.is_file():
            return _read_trim(p, max_chars)
        return ""
    if not USER_PROFILES.is_dir():
        return ""
    for d in sorted(USER_PROFILES.glob(f"*_{telegram_id}")):
        if not d.is_dir():
            continue
        p = d / DIALOG_LOG_FILENAME
        if p.is_file():
            return _read_trim(p, max_chars)
    return ""


def load_dialogy_tail(telegram_id: int, max_chars: int = 7000) -> str:
    """Совместимость: то же, что load_chat_history_tail."""
    return load_chat_history_tail(telegram_id, max_chars)


def build_interlocutor_block(user, admin_id: int) -> str:
    """Кто сейчас пишет + справка + хвост лога диалога."""
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
    traits = load_bloom_traits(pid, max_chars=2800)
    if traits.strip():
        lines.append("")
        if folder:
            hdr = f"=== Наблюдения Блума (user_profiles/{folder}/{TRAITS_FILENAME}) ==="
        else:
            hdr = f"=== Наблюдения Блума (user_profiles/*_{pid}/{TRAITS_FILENAME}) ==="
        lines.append(hdr)
        lines.append(traits)
    dlg = load_dialogy_tail(pid)
    if dlg.strip():
        lines.append("")
        if folder:
            hdr = (
                "=== Недавний диалог с этим человеком "
                f"(user_profiles/{folder}/{DIALOG_LOG_FILENAME}) ==="
            )
        else:
            hdr = (
                "=== Недавний диалог с этим человеком "
                f"(user_profiles/*_{pid}/{DIALOG_LOG_FILENAME}) ==="
            )
        lines.append(hdr)
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
        traits = load_bloom_traits(pid, max_chars=5000)
        if traits.strip():
            part.append(f"--- Наблюдения Блума ({TRAITS_FILENAME}) ---")
            part.append(traits)
        if dlg.strip():
            part.append(f"--- недавний диалог ({DIALOG_LOG_FILENAME}, хвост) ---")
            part.append(dlg)
        blocks.append("\n".join(part))
    return "\n\n".join(blocks) if blocks else ""
