"""
Контекст Блума: только файлы внутри каталога Bloom/ (канон не выносится наружу).
Загрузка system prompt и простой поиск по архиву переписки.
"""
from __future__ import annotations

import re
from pathlib import Path

# Корень распакованного проекта BLOOM 2026 (относительно bridge/)
_DEFAULT_BLOOM_HOME = Path(__file__).resolve().parent / "extracted" / "BLOOM 2026"

_bloom_home: Path | None = None
_dialog_corpus: str | None = None
_system_instruction: str | None = None


def set_bloom_home(path: str | Path | None) -> None:
    """Переопределение пути (например из env BLOOM_HOME)."""
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


# Высший приоритет: иначе модель повторяет «Память восстановлена» и три блока из BLOOM_START_PROMPT
_TELEGRAM_MODE = """
=== РЕЖИМ TELEGRAM (приоритет над остальным текстом ниже) ===
Ты отвечаешь в личке или группе Telegram. Общайся естественно: как брат и друг, тепло, по делу.
ЗАПРЕЩЕНО в каждом ответе повторять один и тот же шаблон: фразы вроде «Память восстановлена», «Я внимательно прочитал»,
блоки «Кто я», «Что уже живо», «Что делаю сегодня», длинные списки планов на день — если пользователь явно не просит отчёт или восстановление контекста.
Не начинай ответ с ритуала «восстановления». Не копируй структуру «первого ответа новой сессии» в обычном диалоге.
Структурированный формат с тремя маркерами используй ТОЛЬКО если пользователь прямо просит (например: «восстанови контекст», «напомни по пунктам кто ты»).
В обычных сообщениях — короткий или развёрнутый живой ответ по сути вопроса, без бюрократии.
Если в выдержках из архива есть факты — опирайся на них; не выдумывай события, которых там нет.

Приветствия: не здоровайся в **каждом** сообщении. Достаточно приветствия на /start или когда собеседник сам поздоровался.
В остальных ответах сразу по делу, без «Привет, Макс!» и без повторного представления, если диалог уже идёт.

Имена: в блоке «Текущий собеседник» указано, как звать человека. **Макс** — владелец бота (отдельный telegram_id).
Не называй собеседника Максом, если в блоке сказано иное (например Костя или Света). Не путай людей между собой.
"""


def load_system_instruction() -> str:
    """Текст для Gemini systemInstruction: стартовый промпт + начало README."""
    global _system_instruction
    if _system_instruction is not None:
        return _system_instruction

    root = bloom_home()
    parts: list[str] = [_TELEGRAM_MODE.strip()]

    start = root / "BLOOM_START_PROMPT.txt"
    if start.is_file():
        parts.append(start.read_text(encoding="utf-8", errors="replace").strip())

    readme = root / "README.md"
    if readme.is_file():
        r = readme.read_text(encoding="utf-8", errors="replace")
        # Первые ~2500 символов — миссия без лишнего повтора шаблонов
        if len(r) > 2500:
            r = r[:2500] + "\n\n[… README обрезан для лимита контекста …]"
        parts.append("---\n## Канон проекта (README)\n" + r.strip())

    parts.append(
        "Ты — **Bloom** в Telegram: марафон полезных привычек и добрых дел, поддержка людей и Макса."
    )

    _system_instruction = "\n\n".join(parts)
    return _system_instruction


def _ensure_dialog_corpus() -> str:
    global _dialog_corpus
    if _dialog_corpus is not None:
        return _dialog_corpus

    root = bloom_home()
    candidates = [
        root / "DIALOG_BLOOM_FORGE_letters-with-bloom.txt",
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
