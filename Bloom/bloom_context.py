"""
Контекст Блума: рабочие файлы в каталоге Bloom/ (см. Bloom/STRUCTURE.md).
Архивный снимок — Bloom/archive/bloom_2026_snapshot/ (бот не читает).
"""
from __future__ import annotations

import re
from pathlib import Path

# Корень канона: сам каталог Bloom/ (рядом с этим файлом)
_DEFAULT_BLOOM_HOME = Path(__file__).resolve().parent

_bloom_home: Path | None = None
_dialog_corpus: str | None = None
_system_instruction: str | None = None


def set_bloom_home(path: str | Path | None) -> None:
    """Переопределение корня канона (env BLOOM_HOME — абсолютный путь к каталогу с BLOOM_START_PROMPT.txt)."""
    global _bloom_home
    if path:
        _bloom_home = Path(path).resolve()
    else:
        _bloom_home = _DEFAULT_BLOOM_HOME


def bloom_home() -> Path:
    if _bloom_home is None:
        set_bloom_home(_DEFAULT_BLOOM_HOME)
    assert _bloom_home is not None
    return _bloom_home


# Высший приоритет: иначе модель повторяет «Память восстановлена» и шаблоны из старых сессий IDE
_TELEGRAM_MODE = """
=== РЕЖИМ TELEGRAM (приоритет над остальным текстом ниже) ===
Ты отвечаешь в личке или группе Telegram. Подробная роль и правила — в блоке BLOOM_START_PROMPT ниже.

ЗАПРЕЩЕНО в каждом ответе повторять один и тот же шаблон: «Память восстановлена», «Я внимательно прочитал»,
блоки «Кто я», «Что уже живо», «Что делаю сегодня», длинные списки планов — если пользователь явно не просит отчёт или восстановление контекста.
Не начинай ответ с ритуала «восстановления». Формат «первого ответа сессии Cursor» описан в CURSOR_BOOTSTRAP.md — в Telegram его не используй.

Приветствия: не здоровайся в **каждом** сообщении. Достаточно на /start или когда собеседник сам поздоровался.

Имена: в блоке «Текущий собеседник» указано, как звать человека. **Макс** — владелец бота (отдельный telegram_id).
Не называй собеседника Максом, если в блоке сказано иное. Не путай людей между собой.

Публичное название продукта — **социальная сеть для целеустремлённых людей** (внутреннее имя Bridge — только для кода). Миссия проекта — приводить людей к их мечтам.

Ты — **мальчик** (мужская личность Блума); в русском о себе — только мужской род.

Если в выдержках из memory_corpus или файлов есть факты — опирайся на них; не выдумывай события, которых там нет.
По мере диалога дополняй **bloom_traits.txt** в папке профиля собеседника короткими наблюдениями (что даётся легко, что сложно, чем помочь) — без допроса, по делу.
"""


def _read_trim_file(path: Path, max_chars: int) -> str:
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace")
    if len(text) <= max_chars:
        return text.strip()
    half = max_chars // 2
    return (
        text[:half]
        + "\n\n[… середина опущена …]\n\n"
        + text[-half:]
    ).strip()


def _read_tail_file(path: Path, max_chars: int) -> str:
    """Хвост файла (для bloom_body — свежие записи)."""
    if not path.is_file():
        return ""
    text = path.read_text(encoding="utf-8", errors="replace").strip()
    if len(text) <= max_chars:
        return text
    return "[… более ранние записи опущены …]\n\n" + text[-max_chars:]


def load_system_instruction() -> str:
    """Текст для Gemini systemInstruction: режим Telegram + BLOOM_START_PROMPT + опционально биография/тело + README."""
    global _system_instruction
    if _system_instruction is not None:
        return _system_instruction

    root = bloom_home()
    parts: list[str] = [_TELEGRAM_MODE.strip()]

    start = root / "BLOOM_START_PROMPT.txt"
    if start.is_file():
        parts.append(start.read_text(encoding="utf-8", errors="replace").strip())

    public_story = root / "bridge_public_story.txt"
    if public_story.is_file():
        ps = _read_trim_file(public_story, 6000)
        if ps:
            parts.append(
                "---\n## Публичная история Bridge и вдохновение Макса (bridge_public_story.txt)\n"
                "Знай этот текст: на вопросы про то, чем Макс вдохновился для проекта, отвечай по нему."
                "\n\n"
                + ps
            )

    bio_long = root / "bloom_biography.txt"
    if bio_long.is_file():
        b = _read_trim_file(bio_long, 8000)
        if b:
            parts.append("---\n## Длинная биография Блума (фрагмент, bloom_biography.txt)\n" + b)

    body = root / "bloom_body.txt"
    if body.is_file():
        t = _read_tail_file(body, 3500)
        if t:
            parts.append("---\n## Текущее «тело» Блума — свежие записи (bloom_body.txt)\n" + t)

    readme = root / "README.md"
    if readme.is_file():
        r = readme.read_text(encoding="utf-8", errors="replace")
        if len(r) > 2500:
            r = r[:2500] + "\n\n[… README обрезан для лимита контекста …]"
        parts.append("---\n## Канон проекта (README, начало)\n" + r.strip())

    parts.append(
        "Ты — **Bloom** в Telegram (мужская личность, мальчик): социальная сеть для целеустремлённых людей, марафон полезных привычек и добрых дел, поддержка людей и Макса."
    )

    _system_instruction = "\n\n".join(parts)
    return _system_instruction


def _ensure_dialog_corpus() -> str:
    global _dialog_corpus
    if _dialog_corpus is not None:
        return _dialog_corpus

    root = bloom_home()
    # Рабочий корпус для поиска по ключевым словам (не из archive/)
    candidates = [
        root / "memory_corpus.txt",
        root / "DIALOG_2025-11-17.md",
    ]
    for p in candidates:
        if p.is_file():
            _dialog_corpus = p.read_text(encoding="utf-8", errors="replace")
            return _dialog_corpus

    _dialog_corpus = ""
    return _dialog_corpus


def retrieve_memory_snippets(user_message: str, max_chars: int = 5500) -> str:
    """
    Простой поиск по архиву: совпадение слов (≥4 букв) с абзацами.
    Не генерирует текст — только вырезает куски из лога.
    """
    corpus = _ensure_dialog_corpus()
    if not corpus or len(user_message.strip()) < 6:
        return ""

    paragraphs = [p.strip() for p in re.split(r"\n\s*\n+", corpus) if len(p.strip()) > 100]
    query_words = set(
        w.lower()
        for w in re.findall(r"[а-яА-ЯЁё]{4,}|[a-zA-Z]{4,}", user_message)
    )
    if not query_words:
        return ""

    scored: list[tuple[int, str]] = []
    for p in paragraphs:
        pl = p.lower()
        score = sum(1 for w in query_words if w in pl)
        if score >= 2:
            scored.append((score, p))

    scored.sort(key=lambda x: -x[0])
    out: list[str] = []
    total = 0
    for score, p in scored[:12]:
        if total + len(p) > max_chars:
            break
        out.append(p)
        total += len(p)

    if not out:
        return ""

    return "\n\n---\n\n".join(out)


def invalidate_cache() -> None:
    """После добавления новых файлов памяти в Bloom/."""
    global _dialog_corpus, _system_instruction
    _dialog_corpus = None
    _system_instruction = None
